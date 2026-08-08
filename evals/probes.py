# evals/probes.py
"""The five investigation primitives, over the pipeline and corpus that already
exist.

An investigation is not allowed to wander. It has exactly these moves:

    retrieve(query)      find evidence by meaning -- the SAME hybrid retrieval
                         /ask uses, never a second ranking that could disagree
    inspect(ref)         read one entity: an indexed chunk, or an exact
                         identifier live-fetched the way .answer() already does
    trace(ref, edge)     follow a proven relationship (evals/entities.py)
    compare(pr)          what the code actually became, from the real per-file
                         diffs of the commits the pull request carries
    verify(claim)        does the evidence support this? -- evals/gate.py,
                         unchanged, which is the only thing allowed to decide

Everything here is a THIN adapter. Not one of these functions ranks, resolves an
entity, or decides what an answer may say: retrieval belongs to the retriever,
relationships to the entity index, and the verdict to the gate. That is what
keeps the investigation loop from quietly becoming a second brain with its own
opinions about the truth.

## Discovery is separated from reading, on purpose

`trace` returns *what it found* as targets, and evidence only for the chunks
that PROVE the relationship. It never pulls in the targets' own text. A single
pull request can name thirty files; reading all of them costs more evidence
budget than the whole investigation has, and most of it answers nothing. So the
loop decides which discovered targets are worth an `inspect`, and pays for text
only when it does. Discovery is cheap and wide; reading is expensive and
narrow.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .entities import EDGE_KINDS
from .gate import gate
from .investigation import EvidenceRef, Step

PRIMITIVES = ("retrieve", "inspect", "trace", "compare", "verify")

_RETRIEVE_K = 6
# The most chunks one retrieve step may ever hold, whatever asked for it. The
# validator bounds a PLANNED step, but retrieve is reachable from seeds too, so
# the ceiling lives here as well -- an unbounded k retains the whole corpus and
# builds a prompt from it.
MAX_RETRIEVE_K = 12
# How many of a file's overlapping windows one inspect may read. A big file is
# indexed as dozens; reading all of them spends the whole evidence budget on one
# file. Bounded and REPORTED (ProbeResult.note), never silently clipped.
_MAX_FILE_WINDOWS = 3
# How many commits one compare() will fetch diffs for. Each is a live GitHub
# call, and a pull request's first few commits carry its substance.
_MAX_COMPARE_COMMITS = 4


@dataclass
class ProbeResult:
    """What one step produced.

    `evidence` is what may be cited; `texts` is the same evidence's text, held
    only for this run (state stores refs, never text -- see
    evals/investigation.py). `discovered` is what was found but NOT read, which
    is what makes the next round adaptive rather than a fixed decision tree.
    `note` carries an honest ceiling -- a truncated list, a lookup that failed --
    so a step that half-worked can never read as one that fully worked.
    """

    evidence: Dict[str, EvidenceRef] = field(default_factory=dict)
    texts: Dict[str, str] = field(default_factory=dict)
    discovered: List[str] = field(default_factory=list)
    note: str = ""

    def add(self, ref: str, text: str, via: str) -> None:
        self.evidence[ref] = EvidenceRef.of(ref, text, via)
        self.texts[ref] = text

    @property
    def chars(self) -> int:
        return sum(len(t) for t in self.texts.values())


@dataclass
class ProbeContext:
    """Everything a probe is allowed to touch. A probe gets no other state --
    it cannot see the investigation's claims or hypotheses, so it cannot tailor
    what it finds to what the investigation already believes."""

    pipeline: object
    entities: object
    token: Optional[str] = None
    # `diff_fetch(number:int, token:str|None) -> Optional[Chunk]` --
    # evals/ingest.fetch_pr_diff, bound by the serving layer. None keeps the
    # probe fully offline (the eval board, every unit test), where compare()
    # falls back to the pull request's commits exactly as it did before.
    diff_fetch: object = None


def _is_entity_ref(value: str) -> bool:
    return ":" in value and value.split(":", 1)[0] in (
        "pr", "issue", "commit", "code", "doc", "config", "index")


def retrieve(ctx: ProbeContext, step: Step) -> ProbeResult:
    query = (step.args.get("query") or "").strip()
    out = ProbeResult()
    if not query:
        out.note = "no query given"
        return out
    k = step.args.get("k") or _RETRIEVE_K
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        k = _RETRIEVE_K
    for ref in ctx.pipeline.search_refs(query, min(k, MAX_RETRIEVE_K)):
        chunk = ctx.pipeline.chunk_for(ref)
        if chunk is not None:
            out.add(ref, chunk.text, step.id)
    if not out.evidence:
        out.note = f"nothing matched {query!r}"
    return out


def inspect(ctx: ProbeContext, step: Step) -> ProbeResult:
    """Read one entity. A ref that is indexed is read from memory; an exact
    identifier that is NOT indexed is live-fetched through the pipeline's own
    fetchers, which is how .answer() already reaches a pull request outside the
    indexed slice. A bare repository path reads that file's windows."""
    target = (step.args.get("ref") or "").strip()
    out = ProbeResult()
    if not target:
        out.note = "no ref given"
        return out

    chunk = ctx.pipeline.chunk_for(target)
    if chunk is not None:
        out.add(target, chunk.text, step.id)
        return out

    if not _is_entity_ref(target):
        # A repository path: read the windows Icarus indexed for it.
        refs = ctx.entities.chunks_for(target)
        for ref in refs[:_MAX_FILE_WINDOWS]:
            c = ctx.pipeline.chunk_for(ref)
            if c is not None:
                out.add(ref, c.text, step.id)
        if len(refs) > _MAX_FILE_WINDOWS:
            out.note = (f"{target} is indexed as {len(refs)} windows; read the "
                        f"first {_MAX_FILE_WINDOWS}")
        elif not refs:
            out.note = f"{target} is not indexed"
        return out

    source, _, rest = target.partition(":")
    live_ref, live_commit = ctx.pipeline.fetchers()
    fetched = None
    try:
        if source in ("pr", "issue") and rest.isdigit() and live_ref is not None:
            fetched = live_ref(int(rest), ctx.token)
        elif source == "commit" and live_commit is not None:
            fetched = live_commit(rest, ctx.token)
    except Exception:
        # A live lookup is best-effort by contract (see ingest.fetch_ref_detail).
        # A failure means this step found nothing, never that the investigation
        # dies -- and it is REPORTED below rather than swallowed into silence.
        fetched = None
    if fetched is None:
        out.note = f"{target} could not be read"
        return out
    # The fetch resolves the KIND -- "#400" can be a pull request or an issue --
    # so trust the ref that came back, not the one that was asked for.
    out.add(fetched.ref, fetched.text, step.id)
    return out


def trace(ctx: ProbeContext, step: Step) -> ProbeResult:
    """Follow one relationship. Evidence is the chunk that PROVES the edge;
    the targets are returned as discoveries for the loop to weigh, not read."""
    ref = (step.args.get("ref") or "").strip()
    edge = (step.args.get("edge") or "").strip()
    out = ProbeResult()
    if edge not in EDGE_KINDS:
        out.note = f"unknown relationship {edge!r}"
        return out
    found = ctx.entities.edges(ref, edge)
    for e in found:
        chunk = ctx.pipeline.chunk_for(e.evidence_ref)
        if chunk is not None:
            out.add(e.evidence_ref, chunk.text, step.id)
        if e.indexed and e.target not in out.discovered:
            out.discovered.append(e.target)
    if not found:
        out.note = f"nothing recorded links {ref} to any {edge}"
    elif ctx.entities.is_truncated(ref, edge):
        out.note = (f"the recorded {edge} list for {ref} is truncated -- this is "
                    f"not everything")
    return out


def compare(ctx: ProbeContext, step: Step) -> ProbeResult:
    """What the code actually became, not just which files were named.

    Two routes, best first:

    1. **The pull request's own diff** (`ingest.fetch_pr_diff`), when a fetcher
       is wired. One request, no dependence on how the repository merges.
    2. **Its commits**, traced and then read live for their per-file patches --
       an indexed commit chunk holds only its MESSAGE (ingest excludes diffs
       deliberately: computing them per commit measured 27s against 2s).

    Route 2 exists because it needs no extra network call when the commits are
    already known, and route 1 exists because route 2 depends on the `(#400)`
    squash-merge subject convention and finds NOTHING in a repository that
    merges differently -- measured on the committed corpus, where most pull
    requests carry no recorded commit link at all.

    When neither route resolves, this says so rather than inventing a diff.
    """
    pr = (step.args.get("pr") or "").strip()
    out = ProbeResult()
    if not pr.startswith("pr:"):
        out.note = "compare needs a pull request"
        return out

    # Ask GitHub for the diff directly when we can. It depends on no merge
    # convention, where the commit route below depends on the `(#400)` squash
    # subject and finds nothing at all in a repository that merges differently.
    number = pr.partition(":")[2]
    if ctx.diff_fetch is not None and number.isdigit():
        try:
            fetched = ctx.diff_fetch(int(number), ctx.token)
        except Exception:
            fetched = None
        if fetched is not None:
            out.add(fetched.ref, fetched.text, step.id)
            return out

    commits = ctx.entities.targets(pr, "commits")
    if not commits:
        out.note = (f"no commit in the index records belonging to {pr}, so its "
                    f"actual changes cannot be read")
        return out
    _, live_commit = ctx.pipeline.fetchers()
    for ref in commits[:_MAX_COMPARE_COMMITS]:
        sha = ref.partition(":")[2]
        fetched = None
        if live_commit is not None:
            try:
                fetched = live_commit(sha, ctx.token)
            except Exception:
                fetched = None
        if fetched is not None:
            out.add(fetched.ref, fetched.text, step.id)
            continue
        # No live access (the offline board, or a failed lookup): the indexed
        # message is still real evidence about the change, and saying so is
        # better than returning nothing.
        chunk = ctx.pipeline.chunk_for(ref)
        if chunk is not None:
            out.add(ref, chunk.text, step.id)
    if len(commits) > _MAX_COMPARE_COMMITS:
        out.note = (f"{pr} has {len(commits)} recorded commits; read the first "
                    f"{_MAX_COMPARE_COMMITS}")
    return out


def verify(claim_text: str, citations, texts: Dict[str, str], question=None) -> bool:
    """Is this claim supported by the evidence it cites?

    Delegates ENTIRELY to evals/gate.py by handing it exactly the shape a writer
    would have produced. There is deliberately no second implementation of
    groundedness here: an investigation that could verify a claim its own gate
    would reject is a system with two different standards of truth, and the
    weaker one always wins in the end.

    `question` is passed only for the FINAL answer, where the gate's why->what
    and entity-presence guards belong. Intermediate claims are checked for
    groundedness alone -- a "what it changed" fact gathered during a "why"
    investigation is not a dodge, and forcing it through the rationale guard
    would discard true findings mid-run. Everything the reader eventually sees
    still passes the full gate at synthesis.
    """
    import json
    payload = json.dumps({"verdict": "answer", "answer": claim_text,
                          "citations": list(citations or ())})
    result = gate(payload, list(texts), question=question, evidence=texts)
    return result.verdict == "answer" and bool(result.citations)


_PROBES = {"retrieve": retrieve, "inspect": inspect, "trace": trace,
           "compare": compare}


def run_step(ctx: ProbeContext, step: Step) -> ProbeResult:
    """One step, never raising into the loop. A probe that fails is a step that
    found nothing and SAYS so -- an investigation that dies on a bad lookup is
    worse than one that reports a gap."""
    fn = _PROBES.get(step.primitive)
    if fn is None:
        return ProbeResult(note=f"unsupported primitive {step.primitive!r}")
    try:
        return fn(ctx, step)
    except Exception as e:            # pragma: no cover - defensive
        return ProbeResult(note=f"{step.primitive} failed: {type(e).__name__}")


def run_round(ctx: ProbeContext, steps: List[Step], max_workers: int = 4):
    """Run independent steps concurrently, returning results in STEP order.

    Concurrency here is worth it because every probe is I/O bound -- a `gh`
    subprocess, an embedding lookup, a live fetch. It is not a multi-agent
    system: the workers share nothing, decide nothing, and the investigation
    state is updated single-threaded after the round joins, so a run is
    reproducible given the same inputs.
    """
    if not steps:
        return []
    if len(steps) == 1:
        return [run_step(ctx, steps[0])]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(lambda s: run_step(ctx, s), steps))
