# evals/test_description_recall.py
"""The description-recall board: can retrieval find evidence when the caller
describes what they want instead of naming it?

WHY THIS EXISTS. Dogfooding Agent Mode on 2026-08-21 produced two live misses on
two different repositories, and neither was a honesty failure -- one abstained,
one answered from lesser evidence, and the gate never passed a false claim. What
failed was RECALL, on the exact journey the MCP tool description advertises: an
agent about to change code asks in prose, never by identifier. Evidence that can
only be reached by number is evidence the product cannot deliver when it counts.

The decisive case is `simonw/sqlite-utils` issue 841, where the maintainer
wrote:

    "(So don't let your agent work on this, I'll do this if and when 5 becomes a
     thing in the future.)"

Nothing in the code or git log records that. Asked by number, Icarus answers it
correctly. Asked "is there any work the maintainer has asked contributors not to
do?", it returned unknown.

WHAT THIS MEASURES, AND WHAT IT DELIBERATELY DOES NOT. Retrieval only: the rank
of a gold ref in `.search(question, k)`, over the SAME stack serving uses
(BM25 + local semantic, RRF-fused, behind the query normalizer). It says nothing
about whether the writer then uses what retrieval found -- case r02 is exactly
that distinction, ranking first here while the live answer ignored it, and the
writer half needs a live model and belongs in its own board.

The fixture is a real corpus, ingested from simonw/sqlite-utils @ 56dd0970 on
2026-08-21 (`evals/fixtures/recall/`), NOT a trimmed one. Trimming to the
"relevant" chunks would delete the competition that ranking is a measurement of.

Self-skips without fastembed, since a lexical-only run measures a different
system than the one that ships.
"""
import json
import unittest
from pathlib import Path

from .corpus import Chunk
from .query_normalize import build_vocabulary
from .retriever import (
    HybridRetriever,
    LexicalRetriever,
    NormalizingRetriever,
    SemanticRetriever,
)

_HERE = Path(__file__).resolve().parent
_QUESTIONS = _HERE / "recall_questions.json"
_K = 10


def _load_board():
    board = json.loads(_QUESTIONS.read_text())
    corpus = _HERE.parent / board["corpus"]
    chunks = [
        Chunk(**json.loads(line))
        for line in corpus.read_text().splitlines()
        if line.strip()
    ]
    return board, chunks


def _build_retriever(chunks):
    """The serving stack, not a simplification of it: `demo/library.py` wraps a
    hybrid retriever in the query normalizer, and measuring anything else would
    measure a system nobody runs."""
    from .provider import make_embedding_provider

    embedder = make_embedding_provider("local")
    hybrid = HybridRetriever(LexicalRetriever(chunks), SemanticRetriever(chunks, embedder))
    return NormalizingRetriever(hybrid, build_vocabulary(chunks))


def _rank(results, gold_refs):
    """1-based rank of the first gold ref, or None."""
    for i, ref in enumerate(results, start=1):
        if ref in gold_refs:
            return i
    return None


class DescriptionRecallBoard(unittest.TestCase):
    """RED where the product does not yet work, and it should stay red until it
    does. Do NOT make these pass by adding the gold ref's wording to the
    question -- that measures the question, not the system."""

    @classmethod
    def setUpClass(cls):
        try:
            import fastembed  # noqa: F401
        except ImportError:                          # pragma: no cover
            raise unittest.SkipTest("fastembed not installed; serving stack unavailable")
        cls.board, cls.chunks = _load_board()
        if not cls.chunks:                           # pragma: no cover
            raise unittest.SkipTest("fixture corpus missing")
        cls.retriever = _build_retriever(cls.chunks)
        cls.ranks = {}
        for case in cls.board["cases"]:
            results = cls.retriever.search(case["question"], _K)
            cls.ranks[case["id"]] = _rank(results, case["gold_refs"])

    def test_every_gold_ref_is_actually_in_the_corpus(self):
        """Without this, a miss below could mean 'never ingested' rather than
        'ranked too low', and those need opposite fixes."""
        present = {c.ref for c in self.chunks}
        for case in self.board["cases"]:
            missing = [r for r in case["gold_refs"] if r not in present]
            self.assertEqual([], missing, f"{case['id']}: gold ref absent from the fixture")

    def test_identifier_phrasing_still_works(self):
        """GREEN, and must stay green. By-number lookup is the working path and
        the reason the misses are a ranking result."""
        for case in self.board["cases"]:
            if case["phrasing"] != "identifier":
                continue
            self.assertIsNotNone(
                self.ranks[case["id"]],
                f"{case['id']}: exact-identifier lookup regressed -- "
                f"{case['gold_refs']} not in top {_K}")

    def test_task_phrasing_reaches_the_evidence(self):
        """GREEN today. Guard: these describe the work in the repository's own
        vocabulary, and if they stop ranking, the intent cases cannot be
        diagnosed separately from a general retrieval regression."""
        for case in self.board["cases"]:
            if case["phrasing"] != "task":
                continue
            self.assertIsNotNone(
                self.ranks[case["id"]],
                f"{case['id']}: {case['gold_refs']} not in top {_K} for a "
                f"task-shaped question")

    def test_intent_phrasing_reaches_the_evidence(self):
        """RED. The product's own promise: the caller asks what they want to
        know, in their words, and the repository's memory answers."""
        misses = []
        for case in self.board["cases"]:
            if case["phrasing"] != "intent":
                continue
            if self.ranks[case["id"]] is None:
                misses.append(f"{case['id']} ({case['gold_refs']}): {case['question']}")
        self.assertEqual(
            [], misses,
            "intent-shaped questions do not reach evidence the corpus provably "
            "holds:\n  " + "\n  ".join(misses))

    def test_board_report(self):
        """Always passes; prints the board so a run is a measurement, not just a
        verdict. Rank is what improves gradually -- a pass/fail alone cannot
        show a fix moving something from 40th to 11th."""
        lines = ["", "description-recall board (rank of gold ref, k=%d)" % _K]
        for case in self.board["cases"]:
            rank = self.ranks[case["id"]]
            lines.append(
                f"  {case['id']}  {case['phrasing']:<10} "
                f"{'rank ' + str(rank) if rank else 'MISS':<8} {case['question'][:58]}")
        print("\n".join(lines))


if __name__ == "__main__":                           # pragma: no cover
    unittest.main()
