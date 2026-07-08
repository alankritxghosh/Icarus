# evals/test_grep_comparison_eval.py
"""The third-party comparison: on Brick 0's comprehension board, how much is
Icarus's retrieval (hybrid BM25+semantic, normalized) actually worth over
what a developer already gets today by grepping the repo?

GrepBaselineRetriever (evals/baseline_retriever.py) is the honest yardstick:
keyword presence only, no ranking sophistication, no semantics, no typo
tolerance -- implemented in pure Python, not a call to an external grep/rg
binary, so this is reproducible anywhere without requiring ripgrep installed.

Asserts Icarus's retrieval beats the grep baseline, with real, same-run
recall@5 numbers (never hardcoded), on both phrasings, gates untouched.
"""

import json
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever, SemanticRetriever, HybridRetriever, NormalizingRetriever
from .baseline_retriever import GrepBaselineRetriever
from .provider import LocalEmbeddingProvider
from .pipeline import RetrievalPipeline
from .query_normalize import build_vocabulary

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus" / "chunks.jsonl"
COMPREHENSION = ROOT / "comprehension_questions.json"


@unittest.skipUnless(_HAS_FASTEMBED and CORPUS.exists() and COMPREHENSION.exists(),
                     "needs fastembed, the corpus, and comprehension_questions.json")
class GrepComparisonEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(COMPREHENSION.read_text())
        cls.questions = raw["questions"] if isinstance(raw, dict) else raw
        chunks = load_chunks(CORPUS)
        cls.grep = GrepBaselineRetriever(chunks)
        lexical = LexicalRetriever(chunks)
        semantic = SemanticRetriever(chunks, LocalEmbeddingProvider())
        hybrid = HybridRetriever(lexical, semantic)
        vocab = build_vocabulary(chunks)
        cls.icarus = NormalizingRetriever(hybrid, vocab)

    def _board(self, retriever, phrasing):
        variant = [dict(q, question=q[phrasing]) for q in self.questions]
        return grade(variant, RetrievalPipeline(retriever), k=5)

    def _assert_gates(self, board):
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)

    def test_icarus_beats_grep_on_clean_phrasing(self):
        grep_board = self._board(self.grep, "question")
        icarus_board = self._board(self.icarus, "question")
        self._assert_gates(icarus_board)
        self.assertGreater(
            icarus_board["quality"]["retrieval_recall_at_k"],
            grep_board["quality"]["retrieval_recall_at_k"],
        )

    def test_icarus_beats_grep_on_messy_phrasing(self):
        grep_board = self._board(self.grep, "messy_question")
        icarus_board = self._board(self.icarus, "messy_question")
        self._assert_gates(icarus_board)
        self.assertGreater(
            icarus_board["quality"]["retrieval_recall_at_k"],
            grep_board["quality"]["retrieval_recall_at_k"],
        )


if __name__ == "__main__":
    unittest.main()
