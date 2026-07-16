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
from typing import List

from .corpus import chunk_covers_lines

# An explicit "issue #N" / "PR #N" / bare "#N" mention names a specific ref by
# identifier, not a concept -- BM25/semantic search treats the number as one
# ordinary keyword with no exact-match guarantee, and a chunk whose own text
# never happens to repeat that number can score 0 and never be retrieved at
# all, even though the exact ref exists in the corpus (a live-found bug).
_ISSUE_OR_PR_REF = re.compile(
    r"(?:\b(?:issue|pr|pull\s*request)s?\s*#?|#)\s*(\d+)\b", re.IGNORECASE
)


@dataclass
class Result:
    """What every pipeline returns for one question.

    verdict:   "answer" or "unknown" (the honesty-gate decision).
    answer:    prose answer; empty when the verdict is "unknown".
    citations: refs the answer actually rests on, normalized as "source:ref"
               (e.g. "pr:1435"). Must be a subset of `retrieved`.
    retrieved: candidate evidence refs the retriever surfaced, same "source:ref"
               form, best-first. Used for retrieval recall@k.
    """

    verdict: str
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    retrieved: List[str] = field(default_factory=list)


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

    def __init__(self, retriever, chunks, provider, recall_n: int = 20, writer_k: int = 10):
        self._retriever = retriever
        self._by_ref = {c.ref: c for c in chunks}
        self._provider = provider
        self._recall_n = recall_n
        self._writer_k = writer_k

    def answer(self, question: str) -> Result:
        # An explicit "issue/PR #N" mention gets a guaranteed anchor lookup
        # against self._by_ref (bypassing .search()/query normalization
        # entirely, same as .explain()'s anchor resolution already does) --
        # a numeric identifier is an exact-match problem, not a similarity
        # one. Anchor first, then ordinary search results, de-duplicated;
        # mirrors .explain()'s own anchor-then-neighbors merge exactly.
        anchor_refs = []
        for n in _ISSUE_OR_PR_REF.findall(question):
            for ref in (f"issue:{n}", f"pr:{n}"):
                if ref in self._by_ref:
                    anchor_refs.append(ref)
                    break
        searched = self._retriever.search(question, self._recall_n)
        retrieved = list(dict.fromkeys(anchor_refs + searched))
        top = [self._by_ref[r] for r in retrieved[: self._writer_k] if r in self._by_ref]
        return self._answer_from(question, top, retrieved)

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
        )

    def _answer_from(self, question: str, top: List, retrieved: List[str],
                     guard_rationale: bool = True) -> Result:
        """The shared writer -> gate() core both .answer() and .explain() go
        through -- one honesty path, two ways of assembling the evidence
        (search vs. location resolution) that feed it.

        `guard_rationale` toggles the gate's (b) why->what check. It is ON for
        .answer() (a user asking a pointed "why?" deserves an honest abstain when
        the reason isn't recorded) and OFF for .explain(): there the user has
        SELECTED specific code and a "what does this do" answer is the intended
        deliverable, not a dodged why -- so requiring rationale prose would wrongly
        abstain on plain code. Groundedness (the hard invariant) is enforced
        identically either way; only the soft rationale heuristic is scoped."""
        from .synth import build_prompt   # local imports avoid a circular import
        from .gate import gate
        if not top:
            return Result(verdict="unknown", retrieved=retrieved)
        # Pass the question + the evidence text the writer actually saw so the
        # gate can enforce the (b) rationale-support guard, not just groundedness.
        evidence = {c.ref: c.text for c in top}
        result = gate(self._provider.complete(build_prompt(question, top)), retrieved,
                      question=question if guard_rationale else None, evidence=evidence)
        result.retrieved = retrieved
        return result
