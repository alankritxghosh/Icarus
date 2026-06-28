# evals/test_retrieval_eval.py
"""The real red->green: against the committed corpus, the lexical pipeline must
lift retrieval recall@k above zero WITHOUT dropping either honesty gate."""

import json
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
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


if __name__ == "__main__":
    unittest.main()
