# evals/test_provider.py
import os
import unittest

from .provider import StaticProvider, OpenRouterProvider, GroqProvider, GeminiProvider
from .provider import _parse_gemini


class StaticProviderTests(unittest.TestCase):
    def test_returns_queued_then_sticks_on_last(self):
        p = StaticProvider(["a", "b"])
        self.assertEqual(p.complete("x"), "a")
        self.assertEqual(p.complete("x"), "b")
        self.assertEqual(p.complete("x"), "b")  # sticks on last

    def test_accepts_a_single_string(self):
        self.assertEqual(StaticProvider("only").complete("x"), "only")


class OpenRouterProviderTests(unittest.TestCase):
    def test_raises_without_api_key(self):
        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                OpenRouterProvider().complete("hi")
        finally:
            if old is not None:
                os.environ["OPENROUTER_API_KEY"] = old


class GroqProviderTests(unittest.TestCase):
    def test_raises_without_api_key(self):
        old = os.environ.pop("GROQ_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                GroqProvider().complete("hi")
        finally:
            if old is not None:
                os.environ["GROQ_API_KEY"] = old


class GeminiProviderTests(unittest.TestCase):
    def test_parse_extracts_text(self):
        data = {"candidates": [{"content": {"parts": [{"text": "the answer"}]}}]}
        self.assertEqual(_parse_gemini(data), "the answer")

    def test_raises_without_api_key(self):
        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                GeminiProvider().complete("hi")
        finally:
            if old is not None:
                os.environ["GEMINI_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
