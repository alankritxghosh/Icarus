# evals/test_answer_correctness.py
"""With a judge supplied, answer_correctness is a real number over the answerable
questions; without one it stays PENDING. A judge never affects the gates."""

import unittest

from .pipeline import Result, Pipeline
from .grader import grade


class _FixedPipeline(Pipeline):
    def __init__(self, by_q):
        self._by_q = by_q

    def answer(self, question):
        return self._by_q[question]


class _StubJudge:
    def __init__(self, correct: bool):
        self._correct = correct

    def is_correct(self, question, reference, candidate):
        return self._correct


QUESTIONS = [
    {"id": "a1", "label": "answerable", "question": "Q1", "reference_answer": "R1",
     "gold_citations": [{"source": "pr", "ref": "1"}]},
    {"id": "u1", "label": "unanswerable", "question": "Q2"},
]


def _answered():
    return _FixedPipeline({
        "Q1": Result(verdict="answer", answer="grounded", citations=["pr:1"], retrieved=["pr:1"]),
        "Q2": Result(verdict="unknown", retrieved=["code:x.py"]),
    })


class AnswerCorrectnessTests(unittest.TestCase):
    def test_pending_without_judge(self):
        board = grade(QUESTIONS, _answered(), k=5)
        self.assertEqual(board["answer_correctness"], "PENDING (manual / judge-later)")

    def test_scored_with_judge(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(True))
        self.assertEqual(board["answer_correctness"], 100.0)

    def test_wrong_answer_scores_zero(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(False))
        self.assertEqual(board["answer_correctness"], 0.0)

    def test_abstention_is_not_correct(self):
        # pipeline abstains on the answerable question -> 0/1 even with a yes-judge
        pipe = _FixedPipeline({
            "Q1": Result(verdict="unknown", retrieved=["pr:1"]),
            "Q2": Result(verdict="unknown", retrieved=[]),
        })
        board = grade(QUESTIONS, pipe, k=5, judge=_StubJudge(True))
        self.assertEqual(board["answer_correctness"], 0.0)

    def test_judge_does_not_break_gates(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(False))
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)


if __name__ == "__main__":
    unittest.main()
