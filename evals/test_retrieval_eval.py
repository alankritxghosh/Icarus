# evals/test_retrieval_eval.py
"""The real red->green: against the committed corpus, the lexical pipeline must
lift retrieval recall@k above zero WITHOUT dropping either honesty gate."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever, SemanticRetriever, HybridRetriever
from .provider import GeminiEmbeddingProvider
from .pipeline import RetrievalPipeline

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(CORPUS.exists(), "corpus not generated; run python3 -m evals.ingest")
class RetrievalEvalTests(unittest.TestCase):
    def setUp(self):
        self.board = grade(QUESTIONS, RetrievalPipeline(LexicalRetriever(load_chunks(CORPUS))), k=5)

    def test_gates_still_hold(self):
        self.assertTrue(self.board["gates_ok"])
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_retrieval_recall_rose_above_zero(self):
        self.assertGreater(self.board["quality"]["retrieval_recall_at_k"], 0.0)


@unittest.skipUnless(os.environ.get("GEMINI_API_KEY") and CORPUS.exists(),
                     "needs GEMINI_API_KEY and the corpus")
class HybridRetrievalEvalTests(unittest.TestCase):
    """Real-model proof (Task C3b): hybrid (BM25 + real Gemini embeddings, fused
    via RRF) must hold both honesty gates at 100% and must not retrieve worse
    than a same-run BM25-only baseline on the labelled set. Embeds every one of
    the committed corpus's chunks with one real network call each (serial, no
    batching/caching -- see evals/retriever.py and the Brick C plan), so this is
    slow and costs real API calls; skipped entirely without GEMINI_API_KEY."""

    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        lexical = LexicalRetriever(chunks)
        semantic = SemanticRetriever(chunks, GeminiEmbeddingProvider())
        hybrid = HybridRetriever(lexical, semantic)
        cls.hybrid_board = grade(QUESTIONS, RetrievalPipeline(hybrid), k=5)
        # Same-run baseline (not a hardcoded historical number) so the comparison
        # stays fair if the corpus or question set ever changes.
        cls.bm25_board = grade(QUESTIONS, RetrievalPipeline(lexical), k=5)

    def test_gates_still_hold(self):
        self.assertTrue(self.hybrid_board["gates_ok"])
        self.assertEqual(self.hybrid_board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.hybrid_board["gates"]["abstention_recall"], 100.0)

    def test_hybrid_recall_at_least_matches_bm25_baseline(self):
        self.assertGreaterEqual(
            self.hybrid_board["quality"]["retrieval_recall_at_k"],
            self.bm25_board["quality"]["retrieval_recall_at_k"],
        )


if __name__ == "__main__":
    unittest.main()
