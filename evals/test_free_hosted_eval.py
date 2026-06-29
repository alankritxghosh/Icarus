# evals/test_free_hosted_eval.py
"""Real-model proof on the free hosted stack: writer = Groq, judge = Gemini.
Both honesty gates must stay 100% and quality must be >= the OpenRouter free
baseline (citation >= 33%, answer >= 50%). Skipped without both keys + corpus."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import GeminiProvider, GroqProvider
from .pipeline import GatedPipeline
from .judge import Judge

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(
    os.environ.get("GEMINI_API_KEY") and os.environ.get("GROQ_API_KEY") and CORPUS.exists(),
    "needs GEMINI_API_KEY, GROQ_API_KEY and the corpus",
)
class FreeHostedEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, GroqProvider())  # writer
        judge = Judge(GeminiProvider())  # judge != writer (cross-provider)
        cls.board = grade(QUESTIONS, pipe, k=5, judge=judge)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_quality_at_least_baseline(self):
        self.assertGreaterEqual(self.board["quality"]["citation_correctness"], 33.0)
        self.assertIsInstance(self.board["answer_correctness"], float)
        self.assertGreaterEqual(self.board["answer_correctness"], 50.0)


if __name__ == "__main__":
    unittest.main()
