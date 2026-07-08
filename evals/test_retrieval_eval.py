# evals/test_retrieval_eval.py
"""The real red->green: against the committed corpus, the lexical pipeline must
lift retrieval recall@k above zero WITHOUT dropping either honesty gate."""

import json
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever, SemanticRetriever, HybridRetriever
from .provider import LocalEmbeddingProvider
from .pipeline import RetrievalPipeline

try:
    import model2vec  # noqa: F401
    _HAS_MODEL2VEC = True
except ImportError:
    _HAS_MODEL2VEC = False

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


@unittest.skipUnless(_HAS_MODEL2VEC and CORPUS.exists(),
                     "needs model2vec (pip install -r requirements.txt) and the corpus")
class HybridRetrievalEvalTests(unittest.TestCase):
    """Real-model proof (Task C3b): hybrid (BM25 + real local model2vec
    embeddings, fused via RRF) must hold both honesty gates at 100% and must
    not retrieve worse than a same-run BM25-only baseline on the labelled set.

    Uses LocalEmbeddingProvider -- the decided FREE route: a local, offline
    static embedding model (no API key, no network after the one-time model
    cache, no quota, no per-request cost). Embeds every committed corpus chunk
    once at construction on plain CPU (milliseconds each, no pacing needed --
    the earlier Gemini path had to pace under a 100 req/min free-tier cap and
    kept exhausting a 1000/day quota; the local model has neither limit). Self-
    skips where model2vec isn't installed."""

    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        lexical = LexicalRetriever(chunks)
        semantic = SemanticRetriever(chunks, LocalEmbeddingProvider())
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
