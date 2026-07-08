# evals/test_query_normalization_eval.py
"""Brick Q's live proof (Task Q2): on Brick 0's comprehension board, wrapping
hybrid retrieval with the query normalizer must never make retrieval worse
(on either phrasing) and, in aggregate, closes the messy-vs-clean recall gap
-- all measured with same-run boards, never hardcoded numbers, honesty gates
untouched throughout.

Honest scope note: this proves AGGREGATE recall parity, not that every single
messy-phrasing question returns the IDENTICAL citation as its clean twin. One
known case in the comprehension set fails on both clean and normalized-messy
phrasing for a reason unrelated to spelling (verbose/diluted phrasing shifting
retrieval weight, not a misspelled token) -- outside a query-normalizer's
scope by design; see the plan doc's Brick Q status note.
"""

import json
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever, SemanticRetriever, HybridRetriever, NormalizingRetriever
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
class QueryNormalizationEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(COMPREHENSION.read_text())
        cls.questions = raw["questions"] if isinstance(raw, dict) else raw
        chunks = load_chunks(CORPUS)
        lexical = LexicalRetriever(chunks)
        semantic = SemanticRetriever(chunks, LocalEmbeddingProvider())
        cls.hybrid = HybridRetriever(lexical, semantic)
        vocab = build_vocabulary(chunks)
        cls.normalized_hybrid = NormalizingRetriever(cls.hybrid, vocab)

    def _board(self, retriever, phrasing):
        variant = [dict(q, question=q[phrasing]) for q in self.questions]
        return grade(variant, RetrievalPipeline(retriever), k=5)

    def _assert_gates(self, board):
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)

    def test_normalization_never_regresses_messy_phrasing_recall(self):
        raw_messy = self._board(self.hybrid, "messy_question")
        normalized_messy = self._board(self.normalized_hybrid, "messy_question")
        self._assert_gates(normalized_messy)
        self.assertGreaterEqual(
            normalized_messy["quality"]["retrieval_recall_at_k"],
            raw_messy["quality"]["retrieval_recall_at_k"],
        )

    def test_normalization_never_regresses_clean_phrasing_recall(self):
        # A normalizer that's always on must be safe for already-correct
        # questions too -- it must never HURT clean phrasing.
        raw_clean = self._board(self.hybrid, "question")
        normalized_clean = self._board(self.normalized_hybrid, "question")
        self._assert_gates(normalized_clean)
        self.assertGreaterEqual(
            normalized_clean["quality"]["retrieval_recall_at_k"],
            raw_clean["quality"]["retrieval_recall_at_k"],
        )

    def test_normalized_messy_recall_reaches_clean_recall_in_aggregate(self):
        # The real, measured claim this brick can honestly make: after
        # normalization, messy-phrasing recall@5 in AGGREGATE is at least
        # clean-phrasing recall@5 (same-run boards, not hardcoded numbers).
        # Not a claim that every individual citation matches its clean twin.
        clean = self._board(self.hybrid, "question")
        normalized_messy = self._board(self.normalized_hybrid, "messy_question")
        self._assert_gates(normalized_messy)
        self.assertGreaterEqual(
            normalized_messy["quality"]["retrieval_recall_at_k"],
            clean["quality"]["retrieval_recall_at_k"],
        )


if __name__ == "__main__":
    unittest.main()
