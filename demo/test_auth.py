# demo/test_auth.py
"""The bearer-token auth helpers. Pure/offline: the GitHub verifier is exercised
through its cache and fail-safe paths without a network call."""

import unittest

from .auth import (
    bearer_token, StaticTokenVerifier, GitHubTokenVerifier, RepoAccessVerifier,
)


class RepoAccessVerifierTests(unittest.TestCase):
    """Entitlement to a repo's index, answered by GitHub rather than modelled here.

    This is what replaces per-user storage as the isolation mechanism, so its
    failure direction is the whole point: anything ambiguous must deny. A bug
    that wrongly denies is an outage; a bug that wrongly allows hands one
    company's private code to another.
    """

    def _clock(self, start=1000.0):
        box = {"t": start}
        return box, (lambda: box["t"])

    def _fn(self, answers, calls):
        """Stand-in for github_access.repo_info: (repo, token) -> dict or None."""
        def access(repo, token):
            calls.append((repo, token))
            return answers.get((repo, token))
        return access

    def test_allows_when_github_says_the_caller_can_read_it(self):
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({("o/r", "tok"): {"private": True}}, calls))
        self.assertTrue(v.can_read("o/r", "tok"))

    def test_denies_when_github_refuses(self):
        # repo_info returns None for 403, 404, network error and malformed body
        # alike -- every one of them must mean "no".
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({}, calls))
        self.assertFalse(v.can_read("o/r", "tok"))

    def test_denies_without_a_token(self):
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({("o/r", None): {"private": False}}, calls))
        self.assertFalse(v.can_read("o/r", None))
        self.assertEqual(calls, [], "must not even ask GitHub without a token")

    def test_second_call_inside_the_ttl_does_not_hit_github(self):
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({("o/r", "tok"): {"private": True}}, calls),
                               ttl=300.0, clock=self._clock()[1])
        v.can_read("o/r", "tok")
        v.can_read("o/r", "tok")
        self.assertEqual(len(calls), 1, "the TTL cache is what keeps us off GitHub's rate limit")

    def test_recheck_after_the_ttl_expires(self):
        calls = []
        box, clock = self._clock()
        v = RepoAccessVerifier(access_fn=self._fn({("o/r", "tok"): {"private": True}}, calls),
                               ttl=300.0, clock=clock)
        v.can_read("o/r", "tok")
        box["t"] += 301.0                      # just past the 5-minute window
        v.can_read("o/r", "tok")
        self.assertEqual(len(calls), 2, "access must be re-verified once the wristband expires")

    def test_revocation_takes_effect_after_the_ttl(self):
        # The accepted risk, pinned as behaviour: access survives up to the TTL
        # after GitHub revokes it, and must stop immediately afterwards.
        calls = []
        answers = {("o/r", "tok"): {"private": True}}
        box, clock = self._clock()
        v = RepoAccessVerifier(access_fn=self._fn(answers, calls), ttl=300.0, clock=clock)
        self.assertTrue(v.can_read("o/r", "tok"))
        answers.clear()                        # GitHub revokes the caller's access
        box["t"] += 299.0
        self.assertTrue(v.can_read("o/r", "tok"), "inside the window, still cached")
        box["t"] += 2.0
        self.assertFalse(v.can_read("o/r", "tok"), "past the window, GitHub is asked again")

    def test_one_callers_grant_never_authorises_another(self):
        # The cache MUST key on token as well as repo. If it keyed on repo alone,
        # the first authorised reader would silently unlock that repo for
        # everyone -- exactly the cross-tenant leak this whole design exists to
        # prevent.
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({("o/r", "mine"): {"private": True}}, calls))
        self.assertTrue(v.can_read("o/r", "mine"))
        self.assertFalse(v.can_read("o/r", "someone-elses"))

    def test_different_repos_are_cached_separately(self):
        calls = []
        v = RepoAccessVerifier(access_fn=self._fn({("o/a", "tok"): {"private": False}}, calls))
        self.assertTrue(v.can_read("o/a", "tok"))
        self.assertFalse(v.can_read("o/b", "tok"))

    def test_a_raising_access_fn_denies_rather_than_propagating(self):
        def boom(repo, token):
            raise RuntimeError("github is down")
        v = RepoAccessVerifier(access_fn=boom)
        self.assertFalse(v.can_read("o/r", "tok"), "an outage must deny, never 500 or allow")


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
