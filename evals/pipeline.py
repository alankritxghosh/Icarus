"""The pipeline interface the harness calls, plus the Phase-1 stub baseline.

A "pipeline" takes a question and returns a Result: a verdict (answer or
abstain), the prose answer, the citations it actually used, and the candidate
evidence it retrieved. The harness in run.py grades that Result against the
labelled set; it never looks inside the pipeline.

The real brain (ingest -> chunk -> embed -> retrieve -> honesty gate ->
synthesize) is the *next* brick. This file only defines the contract and a
do-nothing stub, so we can stand up an honest red baseline first.
"""

from dataclasses import dataclass, field
from typing import List


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
