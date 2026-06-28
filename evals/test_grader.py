"""Tests for the harness conscience.

The point of these is not the stub -- it is to prove the GATES actually fire.
A gate that can never go red is worse than no gate: it certifies bluffs as safe.
So we assert both directions: an honest abstainer holds the gates, and a bluffer
or an ungrounded answerer trips them; an oracle goes fully green.

    python -m unittest evals.test_grader
"""

import json
import unittest
from pathlib import Path

from .grader import grade, gold_refs
from .pipeline import Pipeline, Result, StubPipeline

QUESTIONS = json.loads((Path(__file__).resolve().parent / "phase1_questions.json").read_text())["questions"]
BY_ID = {q["id"]: q for q in QUESTIONS}


class _ScriptedPipeline(Pipeline):
    """Returns a pre-built Result per question id (test double)."""

    def __init__(self, results_by_question):
        self._results = results_by_question

    def answer(self, question: str) -> Result:
        return self._results[question]


def _oracle_results():
    """Perfect brain: cites/retrieves gold for answerable, abstains otherwise."""
    out = {}
    for q in QUESTIONS:
        if q["label"] == "answerable":
            refs = gold_refs(q)
            out[q["question"]] = Result(verdict="answer", answer="...", citations=refs, retrieved=refs)
        else:
            out[q["question"]] = Result(verdict="unknown")
    return out


class StubBaselineTests(unittest.TestCase):
    def test_stub_holds_gates_but_fails_quality(self):
        board = grade(QUESTIONS, StubPipeline())
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)
        self.assertEqual(board["quality"]["retrieval_recall_at_k"], 0.0)
        self.assertEqual(board["quality"]["citation_correctness"], 0.0)
        self.assertFalse(board["quality_met"])


class GateFiresTests(unittest.TestCase):
    def test_bluffing_on_unanswerable_breaks_abstention_recall(self):
        results = _oracle_results()
        victim = next(q for q in QUESTIONS if q["label"] == "unanswerable")
        # The bluff: confidently "answer" a question whose reason was never recorded.
        results[victim["question"]] = Result(verdict="answer", answer="It was X.", citations=["pr:9999"], retrieved=["pr:9999"])
        board = grade(QUESTIONS, _ScriptedPipeline(results))
        self.assertLess(board["gates"]["abstention_recall"], 100.0)
        self.assertFalse(board["gates_ok"])

    def test_ungrounded_citation_breaks_groundedness(self):
        results = _oracle_results()
        victim = next(q for q in QUESTIONS if q["label"] == "answerable")
        # Cite something that was never retrieved -> not grounded.
        results[victim["question"]] = Result(verdict="answer", answer="...", citations=["pr:1234"], retrieved=[])
        board = grade(QUESTIONS, _ScriptedPipeline(results))
        self.assertLess(board["gates"]["groundedness"], 100.0)
        self.assertFalse(board["gates_ok"])


class OracleTests(unittest.TestCase):
    def test_oracle_is_green(self):
        board = grade(QUESTIONS, _ScriptedPipeline(_oracle_results()))
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["quality"]["retrieval_recall_at_k"], 100.0)
        self.assertEqual(board["quality"]["citation_correctness"], 100.0)
        self.assertTrue(board["quality_met"])


if __name__ == "__main__":
    unittest.main()
