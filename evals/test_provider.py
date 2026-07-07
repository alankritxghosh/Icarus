# evals/test_provider.py
import email.message
import os
import unittest
import urllib.error
from unittest import mock

from .provider import StaticProvider, OpenRouterProvider, GroqProvider, GeminiProvider
from .provider import _parse_gemini, make_provider, has_provider_key, _with_retry
from .provider import (
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    StaticEmbeddingProvider,
    make_embedding_provider,
    has_embedding_provider_key,
)


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


class GeminiEmbeddingProviderTests(unittest.TestCase):
    def test_raises_without_api_key(self):
        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                GeminiEmbeddingProvider().embed("hi")
        finally:
            if old is not None:
                os.environ["GEMINI_API_KEY"] = old

    def test_key_goes_in_header_not_url(self):
        req = GeminiEmbeddingProvider()._build_request("hello", key="SECRET123")
        self.assertNotIn("SECRET123", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "SECRET123")

    def test_request_shape(self):
        req = GeminiEmbeddingProvider(model="gemini-embedding-001")._build_request(
            "hello world", key="k"
        )
        self.assertEqual(
            req.full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-embedding-001:embedContent",
        )
        import json as _json
        body = _json.loads(req.data)
        self.assertEqual(body, {"content": {"parts": [{"text": "hello world"}]}})

    def test_parses_embedding_values_from_response(self):
        data = {"embedding": {"values": [0.1, 0.2, 0.3]}}
        self.assertEqual(GeminiEmbeddingProvider._parse_embedding(data), [0.1, 0.2, 0.3])

    def test_embed_goes_through_retry_on_429(self):
        calls = {"n": 0}

        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload

            def read(self):
                import json as _json
                return _json.dumps(self._payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise _http(429)
            return _FakeResp({"embedding": {"values": [1.0, 2.0]}})

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                with mock.patch("time.sleep"):
                    result = GeminiEmbeddingProvider().embed("hello")
        self.assertEqual(result, [1.0, 2.0])
        self.assertEqual(calls["n"], 2)  # first call 429'd, second succeeded


class StaticEmbeddingProviderTests(unittest.TestCase):
    def test_returns_mapped_vector_for_exact_text(self):
        p = StaticEmbeddingProvider({"hello": [1.0, 0.0], "world": [0.0, 1.0]})
        self.assertEqual(p.embed("hello"), [1.0, 0.0])
        self.assertEqual(p.embed("world"), [0.0, 1.0])

    def test_raises_on_unmapped_text(self):
        p = StaticEmbeddingProvider({"hello": [1.0, 0.0]})
        with self.assertRaises(KeyError):
            p.embed("unmapped text")

    def test_accepts_a_callable(self):
        p = StaticEmbeddingProvider(lambda text: [float(len(text))])
        self.assertEqual(p.embed("abc"), [3.0])
        self.assertEqual(p.embed("abcde"), [5.0])


class MakeEmbeddingProviderTests(unittest.TestCase):
    def test_factory_returns_right_class(self):
        self.assertIsInstance(make_embedding_provider("gemini"), GeminiEmbeddingProvider)

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            make_embedding_provider("nope")

    def test_has_embedding_provider_key_reflects_env(self):
        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            self.assertFalse(has_embedding_provider_key("gemini"))
            os.environ["GEMINI_API_KEY"] = "x"
            self.assertTrue(has_embedding_provider_key("gemini"))
        finally:
            os.environ.pop("GEMINI_API_KEY", None)
            if old is not None:
                os.environ["GEMINI_API_KEY"] = old


class EmbeddingPrivateSafeFlagTests(unittest.TestCase):
    """Mirrors PrivateSafeFlagTests: private_safe is construction-time ground
    truth for the trust interlock, never inferred from a key string."""

    def test_gemini_embedding_provider_is_not_private_safe(self):
        self.assertFalse(GeminiEmbeddingProvider().private_safe)  # free tier

    def test_static_embedding_provider_is_private_safe(self):
        self.assertTrue(StaticEmbeddingProvider({}).private_safe)  # offline; nothing leaves

    def test_base_embedding_provider_defaults_to_not_private_safe(self):
        self.assertFalse(EmbeddingProvider().private_safe)

    def test_base_embedding_provider_embed_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            EmbeddingProvider().embed("x")


if __name__ == "__main__":
    unittest.main()
