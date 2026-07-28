"""The pipeline interface the harness calls, plus the Phase-1 stub baseline.

A "pipeline" takes a question and returns a Result: a verdict (answer or
abstain), the prose answer, the citations it actually used, and the candidate
evidence it retrieved. The harness in run.py grades that Result against the
labelled set; it never looks inside the pipeline.

The real brain (ingest -> chunk -> embed -> retrieve -> honesty gate ->
synthesize) is the *next* brick. This file only defines the contract and a
do-nothing stub, so we can stand up an honest red baseline first.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List

from .corpus import chunk_covers_lines

# An explicit "issue #N" / "PR #N" / bare "#N" mention names a specific ref by
# identifier, not a concept -- BM25/semantic search treats the number as one
# ordinary keyword with no exact-match guarantee, and a chunk whose own text
# never happens to repeat that number can score 0 and never be retrieved at
# all, even though the exact ref exists in the corpus (a live-found bug).
_ISSUE_OR_PR_REF = re.compile(
    r"(?:\b(?:issue|pr|pull\s*request)s?\s*#?|#)\s*(\d+)\b", re.IGNORECASE
)

# The KIND the question named, when it named one. GitHub shares a single number
# sequence between issues and pull requests, so issue:N and pr:N can both exist
# for the same N -- and the anchor used to resolve them with a fixed
# ("issue", "pr") order, so the issue silently won every tie no matter what was
# asked. "What did PR 1481 change?" anchored the ISSUE (found 2026-07-28 while
# root-causing a live report). Capturing the word lets the named kind win, and a
# bare "#N" that names no kind keeps the previous precedence unchanged.
_NAMED_REF_KIND = re.compile(
    r"\b(issues?|prs?|pull\s*requests?)\s*#?\s*(\d+)\b", re.IGNORECASE
)


_KIND_WORD = {"issue": "an issue", "pr": "a pull request"}


def _premise_notes(question: str, anchor_refs):
    """Facts derived from which ref ACTUALLY resolved, when the question named a
    different kind for the same number.

    GitHub shares one number sequence between issues and pull requests, so a
    question can be wrong about its own subject: "What did PR 6952 change?" when
    #6952 is an issue. Before this, that produced an honest-but-misleading "no
    one wrote this down" -- the evidence was right there and simply disagreed
    with the question (found live 2026-07-28). Stating the mismatch as a fact
    lets the writer correct it and still cite, which is a GROUNDED answer, not a
    guess: the kind comes from the ref that resolved, never from the model.

    Returns [] when nothing was misnamed, so questions with no mismatch get a
    byte-identical prompt and no behaviour changes anywhere else.
    """
    notes = []
    for word, n in _NAMED_REF_KIND.findall(question or ""):
        asked = "issue" if word.lower().startswith("issue") else "pr"
        for ref in anchor_refs:
            src, _, num = ref.partition(":")
            if num == n and src in _KIND_WORD and src != asked:
                notes.append(f"#{n} is {_KIND_WORD[src]} ({ref}), not "
                             f"{_KIND_WORD[asked]}.")
    return notes


def _preferred_sources(question: str, number: str):
    """Source order to try for `number`, honouring the kind the question named."""
    for word, n in _NAMED_REF_KIND.findall(question or ""):
        if n != number:
            continue
        return ("issue", "pr") if word.lower().startswith("issue") else ("pr", "issue")
    return ("issue", "pr")  # no kind named -- unchanged precedence

# Same exact-identifier problem for a commit SHA, which is never indexed at all
# (see ingest.fetch_commit_detail). Hex-only English words are real ("defaced",
# "decade"), so a bare SHA must contain a digit; an explicit "commit " prefix
# lifts that requirement.
_COMMIT_SHA = re.compile(r"\b(commits?\s+)?([0-9a-fA-F]{7,40})\b")


@dataclass
class Result:
    """What every pipeline returns for one question.

    verdict:   "answer" or "unknown" (the honesty-gate decision).
    answer:    prose answer; empty when the verdict is "unknown".
    citations: refs the answer actually rests on, normalized as "source:ref"
               (e.g. "pr:1435"). Must be a subset of `retrieved`.
    retrieved: candidate evidence refs the retriever surfaced, same "source:ref"
               form, best-first. Used for retrieval recall@k.
    anchored:  the subset of `retrieved` resolved by EXACT LOOKUP rather than by
               search -- because the question named it ("PR 6952") or, in
               .explain(), because the user selected those lines. Always a
               prefix of `retrieved`, and usually empty.
    """

    verdict: str
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    retrieved: List[str] = field(default_factory=list)
    # evidence: {cited ref -> the chunk text the writer actually saw}, for CITED
    # refs only. Lets a caller show the proof itself rather than a pointer to it.
    # Never an input to the honesty gate -- purely what was already used.
    evidence: Dict[str, str] = field(default_factory=dict)
    # anchored: which refs were looked up because the caller NAMED them, split
    # out from the ones search merely suggested. Both already sat in `retrieved`
    # (anchor-first), but a flat list makes a correctly-anchored abstention look
    # identical to one that ignored the question and searched blindly -- reported
    # live 2026-07-28. Display only: nothing here feeds the writer or the gate.
    anchored: List[str] = field(default_factory=list)


class Pipeline:
    """Interface: implementations answer one question at a time."""

    def answer(self, question: str) -> Result:  # pragma: no cover - interface
        raise NotImplementedError


class StubPipeline(Pipeline):
    """The honest red baseline: a brain that knows nothing.

    It always abstains and retrieves nothing. This deliberately PASSES the two
    non-negotiable honesty gates (it never bluffs, so groundedness and
    abstention-recall are trivially 100%) while FAILING every quality metric
    (it retrieves and cites nothing). That failing-on-quality, holding-on-honesty
    board is exactly the baseline the real pipeline must turn green -- without
    ever letting a gate drop. See docs/EVALUATION.md.
    """

    def answer(self, question: str) -> Result:
        return Result(verdict="unknown")


class RetrievalPipeline(Pipeline):
    """Retrieves candidate evidence but does not yet answer.

    Populates `retrieved` so retrieval recall@k can rise, while still abstaining
    (verdict 'unknown', no citations) so groundedness and abstention recall stay
    trivially at 100%. The honesty gate and the writer are the next brick.
    """

    def __init__(self, retriever, top_n: int = 20):
        self._retriever = retriever
        self._top_n = top_n

    def answer(self, question: str) -> Result:
        return Result(verdict="unknown", retrieved=self._retriever.search(question, self._top_n))


class GatedPipeline(Pipeline):
    """Retrieve -> writer (provider) -> deterministic honesty gate -> Result.

    The writer is constrained to answer only from retrieved evidence or abstain;
    the gate (evals/gate.py) enforces that deterministically, failing safe to
    'unknown'. `retrieved` is always the full top-recall_n list so retrieval
    recall@k stays measurable regardless of the verdict.
    """

    # Brick D's default writer prompt when a GitHub selection carries no typed
    # question (the common case: select a line, click "Ask Icarus").
    _DEFAULT_EXPLAIN_QUESTION = "What does this code do, and why is it here?"

    def __init__(self, retriever, chunks, provider, recall_n: int = 20, writer_k: int = 10,
                 live_fetch=None, live_commit_fetch=None):
        self._retriever = retriever
        self._by_ref = {c.ref: c for c in chunks}
        self._provider = provider
        self._recall_n = recall_n
        self._writer_k = writer_k
        # Optional `live_fetch(number:int) -> Optional[Chunk]`: resolves an explicit
        # "PR/issue #N" the corpus never indexed (it caps at the most-recent
        # PR_LIMIT/ISSUE_LIMIT) by fetching that one ref + its comments on demand.
        # None (the eval board / tests) keeps the pipeline fully offline and
        # reproducible; serving binds the real gh-backed fetch (demo/library.py).
        self._live_fetch = live_fetch
        # Optional `live_commit_fetch(sha:str) -> Optional[Chunk]`: resolves an
        # explicit commit SHA, which is NEVER indexed (commits are excluded from
        # ingest by design). Same fail-safe contract as live_fetch.
        self._live_commit_fetch = live_commit_fetch

    def answer(self, question: str) -> Result:
        # An explicit "issue/PR #N" mention gets a guaranteed anchor lookup
        # against self._by_ref (bypassing .search()/query normalization
        # entirely, same as .explain()'s anchor resolution already does) --
        # a numeric identifier is an exact-match problem, not a similarity
        # one. Anchor first, then ordinary search results, de-duplicated;
        # mirrors .explain()'s own anchor-then-neighbors merge exactly.
        anchor_refs = []
        fetched = {}
        for n in _ISSUE_OR_PR_REF.findall(question):
            sources = _preferred_sources(question, n)
            hit = next((f"{s}:{n}" for s in sources if f"{s}:{n}" in self._by_ref), None)
            if hit is not None:
                anchor_refs.append(hit)                 # indexed -> use the cached chunk
            elif self._live_fetch is not None:
                # Not in the indexed slice: fetch that exact PR/issue live. Fail-safe
                # -- a None result just leaves it unanchored, as if unmentioned.
                ch = self._live_fetch(int(n))
                if ch is not None and ch.ref not in fetched:
                    fetched[ch.ref] = ch
                    anchor_refs.append(ch.ref)
        if self._live_commit_fetch is not None:
            for prefix, sha in _COMMIT_SHA.findall(question):
                if not prefix and not any(c.isdigit() for c in sha):
                    continue  # hex-shaped English word, not a SHA
                ch = self._live_commit_fetch(sha)
                if ch is not None and ch.ref not in fetched:
                    fetched[ch.ref] = ch
                    anchor_refs.append(ch.ref)
        searched = self._retriever.search(question, self._recall_n)
        retrieved = list(dict.fromkeys(anchor_refs + searched))
        lookup = {**self._by_ref, **fetched} if fetched else self._by_ref
        top = [lookup[r] for r in retrieved[: self._writer_k] if r in lookup]
        return self._answer_from(question, top, retrieved,
                                 notes=_premise_notes(question, anchor_refs),
                                 anchored=anchor_refs)

    def explain(self, path: str, start: int, end: int, question: str = None) -> Result:
        """Brick D: explain a GitHub line selection, not a free-text question.

        Resolves evidence by LOCATION -- the chunk(s) covering [start, end] in
        `path` (evals/corpus.chunk_covers_lines) -- rather than by `.search()`,
        since a line selection isn't a query. Adds semantic neighbors for
        surrounding context, same as a real /ask: when the caller supplied a
        `question`, neighbors are searched using THAT question -- proven live
        against the real corpus to reproduce .answer()'s exact top-k for the
        identical question (an earlier version always searched on the anchor's
        own code text, which measurably found WORSE neighbors than searching
        the actual question and caused real, reproducible under-answering: the
        writer honestly abstained on a question /ask answers confidently, not
        because evidence didn't exist, but because explain() fed it worse
        evidence). With no question (the common "just click Explain" case),
        there is no natural-language query to search with, so the anchor's own
        text is the best available signal. Then goes through the IDENTICAL
        writer -> gate() path as .answer() via `_answer_from` -- no new
        honesty logic, no special-cased error path. No coverage at all for
        this location -> the gate's ordinary "no top chunks" abstention (an
        honest unknown), exactly like an unanswerable question today.
        """
        anchor = [c for c in self._by_ref.values() if chunk_covers_lines(c, path, start, end)]
        neighbor_query = question or (anchor[0].text if anchor else path)
        neighbor_refs = self._retriever.search(neighbor_query, self._recall_n)

        anchor_refs = [c.ref for c in anchor]
        # Anchor first (most relevant), then neighbors, de-duplicated (the
        # anchor's own text search can find itself) -- one ordered de-dup
        # drives both `top` (Chunk objects, capped at writer_k by the caller)
        # and `retrieved` (refs, for recall@k), so they can never disagree.
        ordered_refs = list(dict.fromkeys(anchor_refs + neighbor_refs))
        top = [self._by_ref[r] for r in ordered_refs if r in self._by_ref]
        retrieved = ordered_refs

        return self._answer_from(
            question or self._DEFAULT_EXPLAIN_QUESTION, top[: self._writer_k], retrieved,
            guard_rationale=False,   # explain delivers the selected code's "what"
            anchored=anchor_refs,    # the chunks covering the user's own selection
        )

    def _answer_from(self, question: str, top: List, retrieved: List[str],
                     guard_rationale: bool = True, notes=None, anchored=None) -> Result:
        """The shared writer -> gate() core both .answer() and .explain() go
        through -- one honesty path, two ways of assembling the evidence
        (search vs. location resolution) that feed it.

        `guard_rationale` toggles the gate's (b) why->what check. It is ON for
        .answer() (a user asking a pointed "why?" deserves an honest abstain when
        the reason isn't recorded) and OFF for .explain(): there the user has
        SELECTED specific code and a "what does this do" answer is the intended
        deliverable, not a dodged why -- so requiring rationale prose would wrongly
        abstain on plain code. Groundedness (the hard invariant) is enforced
        identically either way; only the soft rationale heuristic is scoped.

        `anchored` is carried through untouched for display (see Result). It is
        set on BOTH exits -- an abstention is exactly the case where a reader
        needs to see that the thing they named was in fact looked up."""
        from .synth import build_prompt   # local imports avoid a circular import
        from .gate import gate
        anchored = list(dict.fromkeys(anchored or ()))
        if not top:
            return Result(verdict="unknown", retrieved=retrieved, anchored=anchored)
        # Pass the question + the evidence text the writer actually saw so the
        # gate can enforce the (b) rationale-support guard, not just groundedness.
        evidence = {c.ref: c.text for c in top}
        result = gate(self._provider.complete(build_prompt(question, top, notes=notes)), retrieved,
                      question=question if guard_rationale else None, evidence=evidence)
        result.retrieved = retrieved
        result.anchored = anchored
        # Carry the text of the CITED evidence back out, so a caller can show the
        # proof instead of a pointer to it. Cited-only, and read from the same map
        # the writer and gate saw -- it cannot surface anything that wasn't already
        # grounded, so this adds no new honesty surface.
        result.evidence = {ref: evidence[ref] for ref in result.citations if ref in evidence}
        return result
