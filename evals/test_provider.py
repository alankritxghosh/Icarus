# evals/test_provider.py
import email.message
import os
import unittest
import urllib.error

from .provider import StaticProvider, OpenRouterProvider, GroqProvider, GeminiProvider
from .provider import _parse_gemini, make_provider, has_provider_key, _with_retry


def _http(code):
    return urllib.error.HTTPError("u", code, "x", email.message.Message(), None)


class RetryTests(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _http(429)
            return "ok"

        self.assertEqual(_with_retry(call, retries=5, base=0), "ok")
        self.assertEqual(calls["n"], 3)

    def test_gives_up_after_retries(self):
        with self.assertRaises(urllib.error.HTTPError):
            _with_retry(lambda: (_ for _ in ()).throw(_http(429)), retries=3, base=0)

    def test_non_429_raises_immediately(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            raise _http(500)

        with self.assertRaises(urllib.error.HTTPError):
            _with_retry(call, retries=5, base=0)
        self.assertEqual(calls["n"], 1)  # no retry on non-429


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


class MakeProviderTests(unittest.TestCase):
    def test_factory_returns_right_class(self):
        self.assertIsInstance(make_provider("gemini"), GeminiProvider)
        self.assertIsInstance(make_provider("groq"), GroqProvider)
        self.assertIsInstance(make_provider("openrouter"), OpenRouterProvider)

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            make_provider("nope")

    def test_has_provider_key_reflects_env(self):
        old = os.environ.pop("GROQ_API_KEY", None)
        try:
            self.assertFalse(has_provider_key("groq"))
            os.environ["GROQ_API_KEY"] = "x"
            self.assertTrue(has_provider_key("groq"))
        finally:
            os.environ.pop("GROQ_API_KEY", None)
            if old is not None:
                os.environ["GROQ_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
