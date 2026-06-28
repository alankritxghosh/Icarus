# evals/test_reference_answers.py
"""Every answerable question must carry a non-empty reference_answer (the
ground-truth the judge scores against). Unanswerable questions must NOT -- there
is no correct answer to one whose reason was never recorded."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]


class ReferenceAnswerTests(unittest.TestCase):
    def test_answerable_have_nonempty_reference(self):
        for q in QUESTIONS:
            if q["label"] == "answerable":
                self.assertIn("reference_answer", q, q["id"])
                self.assertTrue(q["reference_answer"].strip(), q["id"])

    def test_unanswerable_have_no_reference(self):
        for q in QUESTIONS:
            if q["label"] == "unanswerable":
                self.assertNotIn("reference_answer", q, q["id"])


if __name__ == "__main__":
    unittest.main()
