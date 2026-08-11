# demo/payload.py
"""Turn a pipeline Result into the JSON the demo page renders.

Answers carry prose + citations (each with a source URL). The honest "unknown"
carries no answer and no citations, but always exposes `searched` (the retrieved
refs) so the abstention is transparent to the viewer -- you can see what it
looked at before it honestly declined.

`anchored` splits out the refs that were looked up because the QUESTION named
them, from the ones search merely suggested. Both are in `searched` (anchors
first), but a flat list made a correctly-anchored abstention -- "PR 6952" looked
up first, exactly as asked -- read as "ignored the question and searched
blindly". Additive: `searched` still lists everything, so "all of them shown"
stays true.
"""

from evals.pipeline import Result

from .links import ref_to_url

# A citation excerpt is PROOF shown inline, not a preview pane: it has to fit a
# small overlay without pushing the answer off screen. Bounded on both axes --
# lines and characters -- because one machine-generated line can be enormous
# (measured up to ~250,000 chars during ingest work) and a line cap alone
# wouldn't catch it.
_EXCERPT_LINES = 4
_EXCERPT_CHARS = 300
_EXCERPT_LINE_CHARS = 96


def excerpt(text: str) -> str:
    """The first few real lines of a cited chunk, bounded for display.

    Truncation is always MARKED with a '…' so the reader can never mistake a
    clipped excerpt for the whole of the evidence -- an unmarked clip would be a
    quiet misrepresentation of the proof, which is the one thing this product
    cannot do.
    """
    if not text:
        return ""
    out, total = [], 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if len(line) > _EXCERPT_LINE_CHARS:
            line = line[:_EXCERPT_LINE_CHARS].rstrip() + "…"
        out.append(line)
        total += len(line)
        if len(out) >= _EXCERPT_LINES or total >= _EXCERPT_CHARS:
            break
    joined = "\n".join(out)
    # Mark the clip whenever anything was dropped, by lines or by characters.
    stripped = [l for l in text.splitlines() if l.strip()]
    if len(stripped) > len(out) or any(len(l.rstrip()) > _EXCERPT_LINE_CHARS for l in stripped[:len(out)]):
        joined += "\n…"
    return joined


def build_payload(result: Result, repo: str, commit: str, indexing: bool = False,
                  include_evidence: bool = False) -> dict:
    """`indexing` marks an answer produced while the search index is still being
    built (lexical only, semantic pending). `include_evidence` lets read-only
    agent clients inspect the bounded chunks that retrieval considered even
    when the honesty gate returns unknown; human clients keep the existing
    citation-only presentation by leaving it false.

    It exists because an abstention in that window means "I have not finished
    reading", which is a DIFFERENT claim from "no one wrote this down" -- and
    this product's whole promise is that the second one is trustworthy. Proven
    live 2026-07-28: the same question abstained mid-window and answered once
    the embed finished, on an identical corpus."""
    citations = []
    if result.verdict == "answer":
        citations = [{"ref": ref,
                      "url": ref_to_url(ref, repo, commit),
                      "excerpt": excerpt(result.evidence.get(ref, ""))}
                     for ref in result.citations]
    payload = {
        # Make every response self-identifying. Agent clients must never infer
        # which active repository happened to serve an answer.
        "repo": repo,
        "commit": commit,
        "verdict": result.verdict,
        "answer": result.answer if result.verdict == "answer" else "",
        "citations": citations,
        "searched": list(result.retrieved),
        "anchored": list(result.anchored),
        "indexing": bool(indexing),
        # WHY it abstained (evals/gate.py's ABSTAIN_* constants), so the
        # unknowns map can separate "nobody recorded this" from "the thing you
        # asked about isn't in this repo". None on an answer.
        "reason": result.abstention_reason if result.verdict == "unknown" else None,
    }
    # The writer's per-sentence self-report, when the caller asked for it
    # (`per_claim`). Additive and ABSENT unless present, so every existing
    # client is byte-identical. Each entry is {text, citations, label} where
    # label is quoted / composed / unsupported -- `composed` means the sentence
    # needs two or more chunks TAKEN TOGETHER, which is the one shape that
    # produced a fabricated answer across four measured Agent Mode tasks and
    # that cannot be recovered after the fact (docs/experiments/2026-08-10-*).
    # It marks a sentence as worth checking; it never asserts one is wrong, and
    # the honesty gate has already passed everything shown here.
    if result.claims:
        payload["claims"] = [
            {"text": c["text"],
             "citations": [{"ref": ref, "url": ref_to_url(ref, repo, commit)}
                           for ref in c["citations"]],
             "label": c["label"],
             # Present ONLY when every citation behind this sentence is a pull
             # request closed without merging -- i.e. it restates a proposal
             # that was refused, not shipped behaviour. Absent otherwise, so
             # existing clients are byte-identical. See evals/pipeline.py.
             **({"rests_on_rejected": True} if c.get("rests_on_rejected") else {})}
            for c in result.claims
        ]
    # Pull requests among the evidence that were CLOSED WITHOUT MERGING. Emitted
    # only when there are any, so every existing client is byte-identical.
    #
    # This is the one thing a full clone cannot supply: a merged PR leaves a
    # commit, a refused one leaves nothing, so `git log` and `git blame` are
    # blind to it. Measured twice as the decisive fact (docs/experiments/
    # 2026-08-10-agent-mode-exp-d*.md) -- once where an agent was about to write
    # a patch two people had already had rejected, once where it declared a live
    # bug fixed because only the merge was visible.
    #
    # Deliberately says WHAT was refused, never WHY: the reason lives in review
    # comments, and asserting one is exactly the composed rationale these
    # experiments caught twice. The caller is pointed at the PR, not told its
    # verdict.
    if result.rejected_attempts:
        payload["rejected_attempts"] = [
            {"ref": a["ref"], "title": a["title"],
             "url": ref_to_url(a["ref"], repo, commit)}
            for a in result.rejected_attempts
        ]
    if include_evidence:
        payload["evidence"] = [
            {
                "ref": ref,
                "url": ref_to_url(ref, repo, commit),
                "excerpt": excerpt(result.evidence.get(ref, "")),
            }
            for ref in result.retrieved
        ]
    return payload


def build_context_payload(package: dict, repo: str, commit: str,
                          indexing: bool = False) -> dict:
    """`package` is `evals.context_package.build_context_package`'s output --
    structured pre-implementation context (Experiment B's `icarus.context
    (task)`, docs/HANDOFF.md), NOT a conversational answer. Wraps it with the
    same self-identifying fields every other payload carries (`repo`/`commit`
    /`indexing`) so an agent client never infers which repo answered -- the
    same discipline `build_payload` documents above.

    Deliberately NOT built on `build_payload`: a context package has no single
    verdict (it can hold decisions AND risks AND unknowns at once), so forcing
    it through the answer/unknown shape would invent a field that does not
    mean anything here."""
    return {"repo": repo, "commit": commit, "indexing": bool(indexing), **package}


def build_investigation_payload(result, investigation, repo: str, commit: str,
                                indexing: bool = False) -> dict:
    """An investigation's answer, in the SAME shape `/ask` returns plus the trail
    that produced it.

    Built on `build_payload` rather than beside it, so every client that can
    already render a cited answer or an honest unknown renders an investigation
    with no change at all -- the extra keys are additive and an older client
    ignores them.

    The additions are the product: a reader can see not only what Icarus
    concluded but HOW the repository led it there. Each finding carries its own
    support class (`explicit` / `strong` / `weak` -- computed in code, see
    evals/investigation.classify_support), so "the repository says this" and "the
    implementation suggests this" are visibly different claims rather than two
    sentences in the same confident voice.
    """
    payload = build_payload(result, repo, commit, indexing=indexing)
    summary = investigation.summary()
    payload["investigation"] = {
        "objective": summary["objective"],
        # What "it" refers to, so a reader can see the follow-up was understood.
        "subject": summary["subject"],
        "findings": [
            {"id": c["id"], "text": c["text"], "support": c["support"],
             "citations": [{"ref": ref, "url": ref_to_url(ref, repo, commit)}
                           for ref in c["citations"]]}
            for c in summary["claims"]
        ],
        "hypotheses": summary["hypotheses"],
        # Published even when empty: "nothing here is unresolved" is a claim
        # worth making explicitly, and a missing key reads as an oversight.
        "unknowns": summary["unknowns"],
        "contradictions": summary["contradictions"],
        "trail": summary["trail"],
        "stopped_because": summary["stopped_because"],
        # Non-null only when a ceiling cut the investigation short. A truncated
        # run must never be presentable as a complete one.
        "incomplete_because": summary["budget_note"],
    }
    return payload
