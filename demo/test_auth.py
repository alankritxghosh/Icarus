# demo/test_auth.py
"""The bearer-token auth helpers. Pure/offline: the GitHub verifier is exercised
through its cache and fail-safe paths without a network call."""

import unittest

from .auth import bearer_token, StaticTokenVerifier, GitHubTokenVerifier


class _Headers(dict):
    """dict with .get already; mimics http headers for bearer_token."""


class BearerTokenTests(unittest.TestCase):
    def test_extracts_bearer(self):
        self.assertEqual(bearer_token(_Headers({"Authorization": "Bearer abc123"})), "abc123")

    def test_case_insensitive_scheme(self):
        self.assertEqual(bearer_token(_Headers({"Authorization": "bearer xyz"})), "xyz")

    def test_missing_header_is_none(self):
        self.assertIsNone(bearer_token(_Headers({})))

    def test_wrong_scheme_is_none(self):
        self.assertIsNone(bearer_token(_Headers({"Authorization": "Basic abc"})))

    def test_empty_token_is_none(self):
        self.assertIsNone(bearer_token(_Headers({"Authorization": "Bearer "})))


class StaticVerifierTests(unittest.TestCase):
    def test_allows_only_listed_tokens(self):
        v = StaticTokenVerifier({"good"})
        self.assertTrue(v.verify("good"))
        self.assertFalse(v.verify("bad"))
        self.assertFalse(v.verify(""))


class GitHubVerifierTests(unittest.TestCase):
    def test_empty_token_never_calls_out(self):
        # No network: an empty token must fail safe without a request.
        self.assertFalse(GitHubTokenVerifier().verify(""))

    def test_cache_hit_skips_network(self):
        v = GitHubTokenVerifier()
        import time
        v._cache["cached"] = time.time() + 300  # pretend GitHub already OK'd it
        self.assertTrue(v.verify("cached"))

    def test_network_error_fails_safe_to_false(self):
        # A transport error must never authorize (fail safe). Patched, offline.
        import urllib.error
        from unittest import mock
        v = GitHubTokenVerifier()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            self.assertFalse(v.verify("anything"))

    def test_expired_cache_entry_is_revalidated_not_trusted(self):
        # An expired entry must not be trusted on its own; with the network down
        # it fails safe to False rather than reusing the stale OK.
        import time
        import urllib.error
        from unittest import mock
        v = GitHubTokenVerifier()
        v._cache["stale"] = time.time() - 1  # expired
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            self.assertFalse(v.verify("stale"))


if __name__ == "__main__":
    unittest.main()
