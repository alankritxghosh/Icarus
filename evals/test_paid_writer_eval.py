# evals/test_paid_writer_eval.py
"""Real-model proof: swapping in the paid Gemini writer must hold the same bar
as the free writer's live proof (evals/test_gated_eval.py) -- both honesty
gates at 100% and citation correctness above zero on the 6 answerable
questions. This proves the model swap doesn't regress anything; it does NOT
prove any data-policy claim about the paid provider. Skipped when
GEMINI_PAID_API_KEY is absent (offline CI)."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import make_provider
from .pipeline import GatedPipeline

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(os.environ.get("GEMINI_PAID_API_KEY") and CORPUS.exists(),
                     "needs GEMINI_PAID_API_KEY and the committed corpus")
class PaidWriterEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, make_provider("gemini-paid"))
        cls.board = grade(QUESTIONS, pipe, k=5)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_citation_correctness_rose(self):
        self.assertGreater(self.board["quality"]["citation_correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
