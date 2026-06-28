# evals/test_judge.py
"""The judge parses a reply into a boolean and fails safe to incorrect when the
reply is ambiguous. The Judge wires a Provider through build_judge_prompt."""

import json
import unittest

from .provider import StaticProvider
from .judge import parse_verdict, Judge


class ParseVerdictTests(unittest.TestCase):
    def test_correct(self):
        self.assertTrue(parse_verdict(json.dumps({"verdict": "correct"})))

    def test_incorrect(self):
        self.assertFalse(parse_verdict(json.dumps({"verdict": "incorrect"})))

    def test_embedded_json(self):
        self.assertTrue(parse_verdict('sure: {"verdict": "correct"} ok'))

    def test_unparseable_fails_safe_to_incorrect(self):
        self.assertFalse(parse_verdict("the model rambled"))

    def test_unknown_value_fails_safe_to_incorrect(self):
        self.assertFalse(parse_verdict(json.dumps({"verdict": "maybe"})))


class JudgeTests(unittest.TestCase):
    def test_judge_returns_bool_from_provider(self):
        j = Judge(StaticProvider(json.dumps({"verdict": "correct"})))
        self.assertTrue(j.is_correct("q", "ref", "cand"))

    def test_judge_fails_safe_when_provider_rambles(self):
        j = Judge(StaticProvider("no json here"))
        self.assertFalse(j.is_correct("q", "ref", "cand"))


if __name__ == "__main__":
    unittest.main()
