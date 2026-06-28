# evals/test_judge_prompt.py
import unittest

from .judge import build_judge_prompt


class BuildJudgePromptTests(unittest.TestCase):
    def setUp(self):
        self.prompt = build_judge_prompt(
            question="Why a new model class?",
            reference="Because other plugins import the old class, so it had to be left alone.",
            candidate="They added a new class to avoid breaking plugins that import the old one.",
        )

    def test_includes_all_three_inputs(self):
        self.assertIn("Why a new model class?", self.prompt)
        self.assertIn("other plugins import", self.prompt)
        self.assertIn("avoid breaking plugins", self.prompt)

    def test_asks_for_a_verdict_token(self):
        self.assertIn("correct", self.prompt.lower())

    def test_truncates_long_candidate(self):
        self.assertLess(len(build_judge_prompt("q", "ref", "x" * 5000)), 4000)


if __name__ == "__main__":
    unittest.main()
