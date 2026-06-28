# evals/test_answer_correctness_eval.py
"""Real-model proof: with the judge, answer_correctness becomes a number > 0 on
the answerable questions while BOTH honesty gates stay at 100%. Skipped without
OPENROUTER_API_KEY or the corpus."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import OpenRouterProvider
from .pipeline import GatedPipeline
from .judge import Judge

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(os.environ.get("OPENROUTER_API_KEY") and CORPUS.exists(),
                     "needs OPENROUTER_API_KEY and the corpus")
class AnswerCorrectnessEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, OpenRouterProvider())
        judge = Judge(OpenRouterProvider(model="poolside/laguna-m.1:free"))  # judge != writer
        cls.board = grade(QUESTIONS, pipe, k=5, judge=judge)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_answer_correctness_is_a_number_above_zero(self):
        self.assertIsInstance(self.board["answer_correctness"], float)
        self.assertGreater(self.board["answer_correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
