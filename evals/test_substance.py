# evals/test_substance.py
"""The substantiveness judge's contract. Stdlib only, always runs."""

import unittest

from .provider import StaticProvider
from .substance import build_substance_prompt, is_substantive, parse_substance


class ParseTests(unittest.TestCase):
    def test_parses_a_substantive_verdict(self):
        self.assertTrue(parse_substance('{"verdict": "substantive"}'))

    def test_parses_a_hollow_verdict(self):
        self.assertFalse(parse_substance('{"verdict": "hollow"}'))

    def test_tolerates_surrounding_prose(self):
        self.assertTrue(parse_substance('Sure!\n{"verdict": "substantive"}\nDone.'))

    def test_fails_safe_to_HOLLOW_not_substantive(self):
        # This judge grades OUR OWN output. An unparseable reply must never
        # inflate the score -- the conservative direction here is to assume the
        # answer said nothing, exactly as evals/judge.py fails safe to
        # "incorrect" rather than "correct".
        for bad in ("", None, "yes it's fine", "{oops", '{"verdict": "maybe"}'):
            self.assertFalse(parse_substance(bad), repr(bad))


class PromptTests(unittest.TestCase):
    def test_the_prompt_carries_the_question_and_the_answer(self):
        p = build_substance_prompt("What stack?", "It uses Python and Click.")
        self.assertIn("What stack?", p)
        self.assertIn("It uses Python and Click.", p)

    def test_the_prompt_names_the_failure_it_is_looking_for(self):
        # The case this exists for, found live: an answer that describes the
        # question's own existence -- "the project asks the question X as part
        # of its onboarding tour" -- citing the file that contains the question
        # string. Grounded, so the honesty gate passed it; useless, so the
        # abstention probe counted a success it should not have.
        p = build_substance_prompt("q", "a")
        self.assertIn("restat", p.lower())

    def test_a_long_answer_is_truncated(self):
        p = build_substance_prompt("q", "x" * 5000)
        self.assertLess(len(p), 4000)


class JudgeTests(unittest.TestCase):
    def test_uses_the_provider_and_returns_its_verdict(self):
        provider = StaticProvider(['{"verdict": "hollow"}'])
        self.assertFalse(is_substantive(provider, "q", "a"))

    def test_an_empty_answer_is_hollow_without_asking_the_model(self):
        # An abstention has no answer text. Spending a judge call on it would
        # be waste, and counting it as substantive would be a lie.
        provider = StaticProvider([])          # would raise if called
        self.assertFalse(is_substantive(provider, "q", "   "))

    def test_a_provider_failure_is_hollow_not_a_crash(self):
        class Boom:
            def complete(self, prompt): raise RuntimeError("provider down")
        self.assertFalse(is_substantive(Boom(), "q", "a real answer"))


if __name__ == "__main__":
    unittest.main()
