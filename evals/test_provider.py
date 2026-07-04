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

    def test_respects_a_small_retry_budget(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            raise _http(429)

        with self.assertRaises(urllib.error.HTTPError):
            _with_retry(call, retries=2, base=0)
        self.assertEqual(calls["n"], 2)  # exactly `retries` attempts, no runaway

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

    def test_key_goes_in_header_not_url(self):
        req = GeminiProvider()._build_request("hello", key="SECRET123")
        self.assertNotIn("SECRET123", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "SECRET123")


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


class PrivateSafeFlagTests(unittest.TestCase):
    """private_safe is a construction-time class property — the interlock's
    ground truth. Free tiers may train on inputs: never True for them."""

    def test_free_providers_are_not_private_safe(self):
        from .provider import OpenRouterProvider, GroqProvider, GeminiProvider
        for cls in (OpenRouterProvider, GroqProvider, GeminiProvider):
            self.assertFalse(cls().private_safe, cls.__name__)

    def test_static_provider_is_private_safe(self):
        from .provider import StaticProvider
        self.assertTrue(StaticProvider("x").private_safe)  # offline; nothing leaves

    def test_base_provider_defaults_to_not_private_safe(self):
        from .provider import Provider
        self.assertFalse(Provider().private_safe)

    def test_paid_gemini_is_private_safe_and_uses_its_own_key(self):
        import os
        from unittest import mock
        from .provider import PaidGeminiProvider
        p = PaidGeminiProvider()
        self.assertTrue(p.private_safe)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "free-key"}, clear=True):
            with mock.patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("should not reach network"),
            ):
                with self.assertRaises(RuntimeError):  # the FREE key must not satisfy it
                    p.complete("hi")

    def test_make_provider_knows_gemini_paid(self):
        import os
        from unittest import mock
        from .provider import make_provider, has_provider_key, PaidGeminiProvider
        self.assertIsInstance(make_provider("gemini-paid"), PaidGeminiProvider)
        with mock.patch.dict(os.environ, {"GEMINI_PAID_API_KEY": "k"}, clear=True):
            self.assertTrue(has_provider_key("gemini-paid"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(has_provider_key("gemini-paid"))


if __name__ == "__main__":
    unittest.main()
