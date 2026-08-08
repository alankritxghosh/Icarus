# evals/investigator.py
"""The investigation loop: frame, gather, read, update, stop, conclude.

    question
       -> subject bound DETERMINISTICALLY from the refs it names
       -> hypotheses proposed (model), seed steps queued (code)
       -> round: probes run concurrently (code)
       ->        each step's evidence read into candidate claims (model)
       ->        every claim verified by evals/gate.py, unverified ones dropped (code)
       ->        support classified, hypotheses scored, contradictions found (code)
       -> stop? (code)  no -> replan (model, validated by code) -> round
       -> answer written from verified findings (model), gated again (code)

## What a model is and is not trusted with

It proposes hypotheses, reads prose into candidate claims, and writes the final
sentence. It never chooses what evidence exists, never resolves an entity, never
scores its own confidence, and never decides to stop. Every step it proposes is
validated against a closed vocabulary before it can run, and every claim it makes
is re-checked by the same honesty gate that guards `/ask`. A model that names a
ref nobody retrieved does not get a worse score here -- its claim is dropped.

## Why the final answer goes through the full gate again

The claims were verified individually for groundedness only, so that a true
"what changed" finding gathered during a "why" investigation is not thrown away
by the rationale guard mid-run. But the sentence the reader actually sees is an
ordinary answer to an ordinary question, so it faces the ordinary gate -- with
the why->what and entity-presence guards on. Nothing reaches a person having
passed a weaker check than `/ask` applies.
"""

import json
from typing import List, Optional

from .gate import extract_json, gate
from .investigation import (
    Budget, Claim, Hypothesis, Investigation, Step, SUPPORT_UNSUPPORTED,
    classify_support,
)
from .pipeline import Result, _ISSUE_OR_PR_REF, _COMMIT_SHA, _preferred_sources
from .entities import EDGE_KINDS
from .probes import MAX_RETRIEVE_K, ProbeContext, run_round, verify
from .synth import build_plan_prompt, build_read_prompt, build_synthesis_prompt

# Relationships worth following from a pull request before anything is known.
# Deliberately a fixed opening, not a model's choice: these four are what an
# engineer opens first on any change, and spending a billed planning call to
# rediscover that every time would be waste. The ADAPTIVE part starts at round
# two, when there is something to adapt to.
_PR_SEEDS = (("linked_issues", "what the change says it was for"),
             ("changed_files", "what it touched"),
             ("commits", "what it actually did"),
             ("subsequent_prs", "what happened to that code afterwards"))

_MAX_PLANNED_STEPS = 4

# How many of one trace's discovered targets are automatically queued for
# reading. Following a relationship and then never looking at what is on the
# other end is the failure this exists to prevent -- measured live, an
# investigation of PR #1525 traced its linked issue, its changed file and its
# follow-up pull requests and read none of them, scoring 25% hop recall while
# reporting itself finished. Leaving that to the planner is leaving the entire
# point of tracing to a model's discretion.
#
# Bounded because a sweeping pull request names dozens of files, and reading all
# of them would spend the whole evidence budget on the least specific evidence
# available. The budget is the real ceiling; this only decides what gets offered.
_MAX_FOLLOW = 3


def _follow_order(targets):
    """Discovered targets, most-informative first.

    A pull request, issue or commit is one bounded document that usually records
    a reason. A file path expands into windows of code that can only ever show
    WHAT, never why. So entities are read before files -- when the budget cuts
    the list short, it should cut the code, not the rationale.
    """
    entities = [t for t in targets if _is_entity(t)]
    return entities + [t for t in targets if not _is_entity(t)]


def _is_entity(target: str) -> bool:
    return target.split(":", 1)[0] in ("pr", "issue", "commit") and ":" in target


# The exact argument shape of each gathering primitive. A whitelist of KEY NAMES
# was not enough: it accepted `retrieve` with trace's arguments and no query at
# all, and it let `k` through as a boolean, a negative, or 1,000,000,000 --
# which reached the production retriever unchanged and retained every chunk it
# returned before the evidence budget was ever consulted.
_STEP_SCHEMA = {
    "retrieve": {"required": ("query",), "optional": ("k",)},
    "inspect": {"required": ("ref",), "optional": ()},
    "trace": {"required": ("ref", "edge"), "optional": ()},
    "compare": {"required": ("pr",), "optional": ()},
}


def _clip_to_budget(out, remaining: int) -> int:
    """Drop whole pieces of a probe's evidence until it fits `remaining`.

    Returns how many were dropped, so the caller can DISCLOSE it. Pieces are
    dropped entire and in the order the probe returned them (best-first for
    retrieval), never sliced: a half-read chunk is text nobody wrote, and
    citing it would misrepresent the evidence rather than merely shorten it.
    """
    dropped = 0
    for ref in list(out.evidence):
        if out.chars <= remaining:
            break
        out.evidence.pop(ref, None)
        out.texts.pop(ref, None)
        dropped += 1
    return dropped


def _validate_step(raw, allowed_refs=None) -> Optional[Step]:
    """One planned step, or None. A model's plan is a SUGGESTION and is treated
    as untrusted input: anything not matching the closed vocabulary and its
    exact argument schema is dropped rather than coerced into something
    runnable, because a coerced step is a lookup nobody asked for.

    `allowed_refs`, when given, is the set of refs the planner was actually
    shown. A step naming anything else is refused: an invented ref cannot
    resolve, so running it spends a step of a bounded budget to learn nothing.
    Seeds bypass this entirely -- they are built in code, from refs the
    deterministic subject binding already resolved.
    """
    if not isinstance(raw, dict):
        return None
    primitive = raw.get("primitive")
    args = raw.get("args")
    schema = _STEP_SCHEMA.get(primitive)
    if schema is None or not isinstance(args, dict):
        return None                       # unknown primitive, or verify
    if set(args) - set(schema["required"]) - set(schema["optional"]):
        return None                       # an argument this primitive cannot take
    clean = {}
    for key in schema["required"]:
        value = args.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        clean[key] = value.strip()
    if "edge" in clean and clean["edge"] not in EDGE_KINDS:
        return None                       # not a relationship that exists
    for ref_key in ("ref", "pr"):
        if ref_key in clean and allowed_refs is not None \
                and clean[ref_key] not in allowed_refs:
            return None
    if "k" in args:
        k = args["k"]
        # bool is an int in Python, so True would otherwise pass as k=1.
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            return None
        clean["k"] = min(k, MAX_RETRIEVE_K)
    reason = raw.get("reason")
    return Step(primitive=primitive, args=clean,
                reason=reason if isinstance(reason, str) else "")


def _anchor_refs(question: str, pipeline) -> List[str]:
    """The refs a question NAMES, resolved by exact lookup.

    Reuses `pipeline`'s own regexes rather than writing new ones, so "PR 400"
    binds to the same ref in an investigation as it does in /ask -- two different
    notions of what a question refers to would be a bug nobody could see.
    """
    refs = []
    for n in _ISSUE_OR_PR_REF.findall(question or ""):
        for source in _preferred_sources(question, n):
            if pipeline.chunk_for(f"{source}:{n}") is not None:
                refs.append(f"{source}:{n}")
                break
        else:
            # Not indexed. It may still be live-fetchable, which inspect() will
            # discover -- name it as a pull request, the commoner case, and let
            # the fetch correct the kind if it is an issue.
            refs.append(f"pr:{n}")
    for prefix, sha in _COMMIT_SHA.findall(question or ""):
        if prefix or any(c.isdigit() for c in sha):
            refs.append(f"commit:{sha}")
    return list(dict.fromkeys(refs))


def _seed_steps(subject: List[str], question: str) -> List[Step]:
    """The opening moves: read the subject, then follow what it is attached to."""
    steps = []
    for ref in subject:
        steps.append(Step("inspect", {"ref": ref}, "read the subject itself"))
        if ref.startswith("pr:"):
            for edge, why in _PR_SEEDS:
                steps.append(Step("trace", {"ref": ref, "edge": edge}, why))
    if not subject:
        steps.append(Step("retrieve", {"query": question}, "find the subject"))
    return steps


def _state_summary(inv: Investigation) -> str:
    """What the planner is shown. Real state only -- established findings, open
    hypotheses, what has already been tried and what is still unknown."""
    lines = []
    established = [c for c in inv.claims if c.verified]
    lines.append("ESTABLISHED SO FAR:" if established else "ESTABLISHED SO FAR: nothing yet")
    lines += [f"- ({c.support}) {c.text}" for c in established[:12]]
    if inv.hypotheses:
        lines.append("\nHYPOTHESES:")
        lines += [f"- [{h.id}] {h.statement} -- {h.status}" for h in inv.hypotheses]
    if inv.unknowns:
        lines.append("\nSTILL UNKNOWN:")
        lines += [f"- {u}" for u in inv.unknowns[:8]]
    if inv.performed:
        lines.append("\nALREADY TRIED (do not repeat):")
        lines += [f"- {s.primitive} {json.dumps(s.args, sort_keys=True)}"
                  for s in inv.performed]
    return "\n".join(lines)


def _plan(inv: Investigation, provider, known_refs) -> int:
    """Ask for hypotheses and next steps. Returns how many steps were queued.

    Everything the model returns is validated; a plan of pure nonsense queues
    nothing and the loop stops on its own. That is the intended failure mode --
    an investigation that cannot plan should end, not improvise.
    """
    inv.budget.spend_writer()
    data = extract_json(provider.complete(
        build_plan_prompt(inv.objective, _state_summary(inv), known_refs)))
    if not isinstance(data, dict):
        return 0
    for statement in (data.get("hypotheses") or [])[:5]:
        if not isinstance(statement, str) or not statement.strip():
            continue
        if any(h.statement == statement.strip() for h in inv.hypotheses):
            continue
        inv.hypotheses.append(
            Hypothesis(id=f"h{len(inv.hypotheses) + 1}", statement=statement.strip()))
    queued = 0
    for raw in (data.get("steps") or [])[:_MAX_PLANNED_STEPS]:
        step = _validate_step(raw, allowed_refs=set(known_refs or ()))
        if step is not None and inv.queue(step):
            queued += 1
    return queued


def _read(inv: Investigation, provider, texts, note, counter) -> None:
    """Turn one step's evidence into verified claims. Anything the gate will not
    stand behind never enters the state at all."""
    inv.budget.spend_writer()
    data = extract_json(provider.complete(
        build_read_prompt(inv.objective, inv.hypotheses, texts, note)))
    if not isinstance(data, dict):
        return
    for raw in (data.get("claims") or []):
        if not isinstance(raw, dict):
            continue
        text = raw.get("text")
        citations = raw.get("citations")
        if not isinstance(text, str) or not text.strip():
            continue
        if isinstance(citations, str):
            citations = [citations]
        if not isinstance(citations, list):
            continue
        # Groundedness only at this stage -- see the module docstring.
        if not verify(text.strip(), citations, texts):
            continue
        cites = [c for c in citations if isinstance(c, str)]
        # Classified BEFORE it is admitted: a claim citing nothing the
        # investigation retained cannot be shown to anyone, so it never enters
        # the state (and never leaves a dangling id on a hypothesis).
        if classify_support(cites, inv.evidence) == SUPPORT_UNSUPPORTED:
            continue
        hid = raw.get("hypothesis")
        counter[0] += 1
        inv.add_claim(Claim(id=f"c{counter[0]}", text=text.strip(), citations=cites,
                            hypothesis_id=hid if inv.hypothesis(hid) else None,
                            polarity=raw.get("supports") is not False,
                            verified=True))
    for unknown in (data.get("unknowns") or [])[:5]:
        if isinstance(unknown, str) and unknown.strip() \
                and unknown.strip() not in inv.unknowns:
            inv.unknowns.append(unknown.strip())


def investigate(question: str, pipeline, entities, provider, token: str = None,
                budget: Budget = None, subject: List[str] = None,
                objective: str = None, carried=None, diff_fetch=None,
                texts=None) -> Investigation:
    """Run one investigation to a stopping point and return its state.

    `subject`/`objective` let a follow-up turn continue an existing enquiry
    ("why did IT change?") without re-deriving what "it" is.

    `texts` is a caller-owned dict that this fills with the text of every piece
    of evidence gathered, keyed by ref. It is a parameter rather than state on
    the Investigation because the state deliberately holds refs and never text
    (see evals/investigation.py) -- but the caller needs the text to conclude
    and to show excerpts, and rebuilding it from the indexed corpus afterwards
    silently LOSES everything that was live-fetched: a pull request outside the
    indexed slice, a commit, a diff. Found live 2026-08-08 running compare()
    end to end, where `diff:1525` reached the conclusion with empty text, which
    both blanked its excerpt and left the gate's entity-presence guard checking
    an empty string.

    `carried` are findings earlier turns already established (demo/investigations
    .CarriedClaim). They enter as verified claims so this turn COMPOUNDS instead
    of restarting: the planner sees what is already known and spends its steps on
    something new, and the conclusion can draw on the whole conversation rather
    than only the last question.

    Each carries the support class it was measured with, and it is NOT
    reclassified. It was computed against the evidence that turn actually held;
    re-deriving it now, against evidence this turn happens to hold, would restate
    an old finding at a strength nothing ever measured -- and would usually
    downgrade it to unsupported for no better reason than that the text was
    deliberately not kept.
    """
    inv = Investigation(objective=objective or question, question=question,
                        budget=budget or Budget())
    inv.subject = list(subject or _anchor_refs(question, pipeline))
    for i, prior in enumerate(carried or (), start=1):
        # Deliberately not attached to any hypothesis: this turn's hypotheses are
        # new, and an id from a previous turn would attach a finding to whatever
        # happens to hold that slot now.
        inv.claims.append(Claim(id=f"p{i}", text=prior.text,
                                citations=list(prior.citations),
                                support=prior.support, verified=True))
    ctx = ProbeContext(pipeline=pipeline, entities=entities, token=token,
                       diff_fetch=diff_fetch)
    texts = texts if texts is not None else {}
    counter = [0]

    for step in _seed_steps(inv.subject, question):
        inv.queue(step)

    known_refs = list(inv.subject)
    if inv.budget.allows_gathering_writer():
        _plan(inv, provider, known_refs)

    while inv.should_stop() is None:
        batch = inv.take_round()
        if not batch:
            break
        results = run_round(ctx, batch, max_workers=inv.budget.max_parallel)
        new_refs = 0
        for step, out in zip(batch, results):
            inv.performed.append(step)
            # The evidence ceiling is applied HERE, before anything is retained,
            # because a probe cannot know what the rest of its round already
            # spent. Dropping whole pieces rather than slicing text keeps every
            # retained chunk complete: half a chunk is evidence nobody wrote.
            dropped = _clip_to_budget(out, inv.budget.remaining_evidence_chars())
            inv.budget.spend_step(chars=out.chars)
            new_refs += inv.absorb(out.evidence)
            texts.update(out.texts)
            if dropped:
                # Disclosed, never silent: a conclusion drawn from a partial
                # read must not be presentable as one drawn from the whole.
                note = (f"{dropped} piece{'s' if dropped != 1 else ''} of evidence "
                        f"went unread -- the investigation reached its evidence limit")
                if note not in inv.unknowns:
                    inv.unknowns.append(note)
            for ref in out.discovered:
                if ref not in known_refs:
                    known_refs.append(ref)
            # Read what the trace found. Deterministic on purpose: following a
            # relationship and then not looking at the other end is the whole
            # failure mode (see _MAX_FOLLOW), and it must not depend on a model
            # remembering to propose the obvious next step.
            if step.primitive == "trace":
                for target in _follow_order(out.discovered)[:_MAX_FOLLOW]:
                    inv.queue(Step("inspect", {"ref": target},
                                   f"read what {step.args.get('ref')} "
                                   f"{step.args.get('edge')} led to"))
            if out.note and out.note not in inv.unknowns and not out.evidence:
                # A step that found nothing is a finding: it says the repository
                # does not record this. Kept as an unknown so it reaches the
                # answer instead of vanishing.
                inv.unknowns.append(out.note)
            if out.evidence and inv.budget.allows_gathering_writer():
                _read(inv, provider, out.texts, out.note, counter)
        inv.rescore()
        inv.detect_contradictions()
        inv.note_round(new_refs)
        if inv.should_stop() is None and inv.budget.allows_gathering_writer():
            _plan(inv, provider, known_refs[:60])

    inv.stopped_because = inv.should_stop()
    return inv


def conclude(inv: Investigation, provider, texts=None) -> Result:
    """Write the answer from the investigation's verified findings.

    Returns an ordinary `Result`, so every existing caller -- the payload
    builder, the citation renderer, the Mac app -- renders an investigation with
    the code it already has. The gate runs with the real question, so the full
    set of guards applies to what the reader sees.
    """
    findings = [c for c in inv.claims if c.verified and c.support != SUPPORT_UNSUPPORTED]
    retrieved = list(inv.evidence)
    if not findings:
        from .gate import ABSTAIN_NO_EVIDENCE
        return Result(verdict="unknown", retrieved=retrieved, anchored=list(inv.subject),
                      abstention_reason=ABSTAIN_NO_EVIDENCE)
    if not inv.budget.allows_writer():
        # The gathering half overspent its share, so there is no capacity to
        # write a conclusion. Say so as an honest unknown rather than making an
        # eleventh call on a ten-call budget.
        from .gate import ABSTAIN_NO_EVIDENCE
        return Result(verdict="unknown", retrieved=retrieved,
                      anchored=list(inv.subject),
                      abstention_reason=ABSTAIN_NO_EVIDENCE)
    inv.budget.spend_writer()
    raw = provider.complete(build_synthesis_prompt(
        inv.question or inv.objective, findings, unknowns=inv.unknowns,
        contradictions=[about for _, _, about in inv.contradictions],
        budget_note=inv.budget.exhausted_reason()))
    evidence = {ref: (texts or {}).get(ref, "") for ref in retrieved}
    result = gate(raw, retrieved, question=inv.question or inv.objective,
                  evidence=evidence if texts else None)
    result.retrieved = retrieved
    result.anchored = list(inv.subject)
    if texts:
        result.evidence = {r: texts[r] for r in result.citations if r in texts}
    return result
