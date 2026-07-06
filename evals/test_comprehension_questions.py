# evals/test_comprehension_questions.py
"""Schema/loader test for the Brick 0 code-comprehension probe set.

This is the probe that measures whether Icarus understands the code itself
(what/how questions), asked in both clean and deliberately messy phrasing, so
later bricks (whole-codebase ingest, semantic retrieval, query-understanding)
have a concrete red baseline to turn green. Mirrors test_reference_answers.py's
structure but adds the messy_question and citations-exist-in-corpus checks this
new file's spec requires.
"""

import json
import unittest
from pathlib import Path

from .corpus import load_chunks

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "comprehension_questions.json").read_text())["questions"]
CORPUS_PATH = ROOT / "corpus" / "chunks.jsonl"


class ComprehensionQuestionsTests(unittest.TestCase):
    def test_at_least_12_answerable_and_2_unanswerable(self):
        answerable = [q for q in QUESTIONS if q["label"] == "answerable"]
        unanswerable = [q for q in QUESTIONS if q["label"] == "unanswerable"]
        self.assertGreaterEqual(len(answerable), 12)
        self.assertGreaterEqual(len(unanswerable), 2)

    def test_answerable_have_nonempty_citations_and_reference(self):
        for q in QUESTIONS:
            if q["label"] == "answerable":
                self.assertIn("citations", q, q["id"])
                self.assertTrue(q["citations"], q["id"])
                self.assertIn("reference_answer", q, q["id"])
                self.assertTrue(q["reference_answer"].strip(), q["id"])

    def test_unanswerable_have_no_citations_or_reference(self):
        for q in QUESTIONS:
            if q["label"] == "unanswerable":
                self.assertFalse(q.get("citations"), q["id"])
                self.assertNotIn("reference_answer", q, q["id"])

    def test_every_question_has_a_genuinely_messy_variant(self):
        for q in QUESTIONS:
            self.assertIn("messy_question", q, q["id"])
            messy = q["messy_question"]
            self.assertTrue(messy.strip(), q["id"])
            self.assertNotEqual(messy, q["question"], q["id"])

    def test_answerable_citations_exist_in_real_corpus(self):
        real_refs = {c.ref for c in load_chunks(CORPUS_PATH)}
        for q in QUESTIONS:
            if q["label"] == "answerable":
                for ref in q["citations"]:
                    self.assertIn(ref, real_refs, f"{q['id']}: {ref}")


if __name__ == "__main__":
    unittest.main()
