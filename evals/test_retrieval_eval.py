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
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"
COMPREHENSION = ROOT / "comprehension_questions.json"


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


@unittest.skipUnless(_HAS_FASTEMBED and CORPUS.exists(),
                     "needs fastembed (pip install -r requirements.txt) and the corpus")
class HybridRetrievalEvalTests(unittest.TestCase):
    """No-regression + gates guard (Task C3b) on the phase1 board: hybrid
    (BM25 + real local ONNX embeddings, fused via RRF) must hold both honesty
    gates at 100% and never retrieve worse than a same-run BM25-only baseline.

    Uses LocalEmbeddingProvider -- the decided FREE route: a local, offline ONNX
    transformer via fastembed (no API key, no network after the one-time model
    cache, no quota, no per-request cost). Embeds every committed corpus chunk
    once at construction on CPU -- no pacing/quota (the earlier Gemini path had
    to pace under a 100 req/min cap and kept exhausting a 1000/day quota). The
    phase1 board is why-heavy and BM25 already ceilings on it, so this class is
    the regression floor; HybridComprehensionEvalTests below proves the actual
    semantic *lift*. Self-skips where fastembed isn't installed."""

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


@unittest.skipUnless(_HAS_FASTEMBED and CORPUS.exists() and COMPREHENSION.exists(),
                     "needs fastembed, the corpus, and comprehension_questions.json")
class HybridComprehensionEvalTests(unittest.TestCase):
    """The genuine semantic-lift proof (remarks 6/8) on Brick 0's comprehension
    board -- real what/how questions where BM25 does NOT ceiling. Proves, with
    same-run baselines (never hardcoded numbers), that local ONNX semantic
    retrieval actually BEATS keyword search:

      - clean phrasing: hybrid recall@5 STRICTLY exceeds BM25 (semantic adds
        real signal, not just non-regression);
      - messy phrasing (typos/broken grammar): hybrid STRICTLY exceeds BM25 --
        the robustness-to-phrasing win, since BM25 collapses on typos while the
        embedding does not;
      - both honesty gates stay at 100% under semantic retrieval, on both
        phrasings.

    The embedding model is built ONCE (embeds all corpus chunks) and reused for
    both phrasings. Self-skips without fastembed / the corpus / the set."""

    @classmethod
    def setUpClass(cls):
        raw = json.loads(COMPREHENSION.read_text())
        cls.questions = raw["questions"] if isinstance(raw, dict) else raw
        chunks = load_chunks(CORPUS)
        cls.lexical = LexicalRetriever(chunks)
        semantic = SemanticRetriever(chunks, LocalEmbeddingProvider())
        cls.hybrid = HybridRetriever(cls.lexical, semantic)

    def _boards(self, phrasing):
        variant = [dict(q, question=q[phrasing]) for q in self.questions]
        hybrid = grade(variant, RetrievalPipeline(self.hybrid), k=5)
        bm25 = grade(variant, RetrievalPipeline(self.lexical), k=5)
        return hybrid, bm25

    def _assert_gates(self, board):
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)

    def test_clean_phrasing_hybrid_beats_bm25_with_gates_intact(self):
        hybrid, bm25 = self._boards("question")
        self._assert_gates(hybrid)
        self.assertGreater(
            hybrid["quality"]["retrieval_recall_at_k"],
            bm25["quality"]["retrieval_recall_at_k"],
        )

    def test_messy_phrasing_hybrid_beats_bm25_with_gates_intact(self):
        hybrid, bm25 = self._boards("messy_question")
        self._assert_gates(hybrid)
        self.assertGreater(
            hybrid["quality"]["retrieval_recall_at_k"],
            bm25["quality"]["retrieval_recall_at_k"],
        )


if __name__ == "__main__":
    unittest.main()
