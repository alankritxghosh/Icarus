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
    def test_maps_tokens_to_user_ids(self):
        v = StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"})
        self.assertEqual(v.verify("tok-a"), "1001")
        self.assertEqual(v.verify("tok-b"), "1002")
        self.assertIsNone(v.verify("bad"))
        self.assertIsNone(v.verify(""))

    def test_set_input_means_token_is_its_own_id(self):
        # Back-compat sugar for tests that don't care about the id value.
        v = StaticTokenVerifier({"good"})
        self.assertEqual(v.verify("good"), "good")


class GitHubVerifierTests(unittest.TestCase):
    def test_empty_token_never_calls_out(self):
        self.assertIsNone(GitHubTokenVerifier().verify(""))

    def test_cache_hit_returns_id_without_network(self):
        import time
        v = GitHubTokenVerifier()
        v._cache["cached"] = ("77", time.time() + 300)
        self.assertEqual(v.verify("cached"), "77")

    def test_valid_token_returns_the_github_user_id(self):
        import io
        from unittest import mock

        class _Resp(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch("urllib.request.urlopen",
                        return_value=_Resp(b'{"id": 583231, "login": "octocat"}')):
            self.assertEqual(GitHubTokenVerifier().verify("tok"), "583231")

    def test_network_error_fails_safe_to_none(self):
        import urllib.error
        from unittest import mock
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            self.assertIsNone(GitHubTokenVerifier().verify("anything"))

    def test_malformed_body_fails_safe_to_none(self):
        import io
        from unittest import mock

        class _Resp(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch("urllib.request.urlopen", return_value=_Resp(b"not json")):
            self.assertIsNone(GitHubTokenVerifier().verify("tok"))

    def test_expired_cache_entry_is_revalidated_not_trusted(self):
        import time
        import urllib.error
        from unittest import mock
        v = GitHubTokenVerifier()
        v._cache["stale"] = ("77", time.time() - 1)
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            self.assertIsNone(v.verify("stale"))


if __name__ == "__main__":
    unittest.main()
