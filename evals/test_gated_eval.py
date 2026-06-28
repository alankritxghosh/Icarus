# evals/test_gated_eval.py
"""Real-model proof: the gated pipeline must lift citation correctness above
zero on the 6 answerable questions while keeping BOTH honesty gates at 100% --
including honest abstention on the 4 unrecorded code questions. Skipped when
OPENROUTER_API_KEY is absent (offline CI)."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import OpenRouterProvider
from .pipeline import GatedPipeline

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(os.environ.get("OPENROUTER_API_KEY") and CORPUS.exists(),
                     "needs OPENROUTER_API_KEY and the corpus")
class GatedEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, OpenRouterProvider())
        cls.board = grade(QUESTIONS, pipe, k=5)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_citation_correctness_rose(self):
        self.assertGreater(self.board["quality"]["citation_correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
