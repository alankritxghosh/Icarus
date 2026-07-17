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
    StaticEmbeddingProvider,
    LocalEmbeddingProvider,
    make_embedding_provider,
)

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False


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
    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            make_embedding_provider("nope")


class EmbeddingPrivateSafeFlagTests(unittest.TestCase):
    """Mirrors PrivateSafeFlagTests: private_safe is construction-time ground
    truth for the trust interlock, never inferred from a key string."""

    def test_static_embedding_provider_is_private_safe(self):
        self.assertTrue(StaticEmbeddingProvider({}).private_safe)  # offline; nothing leaves

    def test_base_embedding_provider_defaults_to_not_private_safe(self):
        self.assertFalse(EmbeddingProvider().private_safe)

    def test_base_embedding_provider_embed_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            EmbeddingProvider().embed("x")

    def test_local_embedding_provider_is_private_safe(self):
        # A class-level declaration checkable without constructing (which would
        # load the model): the local embedder never egresses text, so it is the
        # strongest private-safe case -- stronger than any hosted tier.
        self.assertTrue(LocalEmbeddingProvider.private_safe)

    @unittest.skipUnless(_HAS_FASTEMBED, "fastembed not installed")
    def test_make_embedding_provider_builds_local(self):
        # 'local' is registered in the factory (constructing it loads the model,
        # so this needs fastembed).
        self.assertIsInstance(make_embedding_provider("local"), LocalEmbeddingProvider)


@unittest.skipUnless(_HAS_FASTEMBED, "fastembed not installed")
class LocalEmbeddingProviderLiveTests(unittest.TestCase):
    """Real, offline proof (no network after the one-time model cache, no key,
    no quota) that LocalEmbeddingProvider produces genuine SEMANTIC embeddings:
    a paraphrase with ZERO keyword overlap must land closer to the query than an
    unrelated sentence -- the exact property BM25 cannot deliver and the reason
    Brick C exists. Self-skips where fastembed isn't installed."""

    @classmethod
    def setUpClass(cls):
        cls.p = LocalEmbeddingProvider()

    @staticmethod
    def _cos(a, b):
        import math
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    def test_embed_returns_plain_list_of_floats(self):
        v = self.p.embed("authenticate the user")
        self.assertIsInstance(v, list)
        self.assertGreater(len(v), 0)
        self.assertTrue(all(isinstance(x, float) for x in v))

    def test_paraphrase_beats_unrelated_with_zero_keyword_overlap(self):
        q = self.p.embed("how does the tool authenticate a user")
        related = self.p.embed("the login flow verifies credentials and issues a session token")
        unrelated = self.p.embed("the recipe calls for two cups of flour and a pinch of salt")
        self.assertGreater(self._cos(q, related), self._cos(q, unrelated))


if __name__ == "__main__":
    unittest.main()
