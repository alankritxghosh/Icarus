# evals/test_github_access.py
"""The private-repo permission gate: GET /repos/{owner}/{repo} AS THE CALLER.
200 -> {"private": bool}; anything else -> None (fail-safe refuse). Offline:
the opener is injected."""

import io
import json
import unittest
import urllib.error

from .github_access import commits_between, head_commit, repo_info


class _Resp(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener_returning(status, body):
    captured = {}

    def opener(req, timeout):
        captured["req"] = req
        return _Resp(status, body)

    return opener, captured


class RepoInfoTests(unittest.TestCase):
    def test_200_private_true(self):
        opener, _ = _opener_returning(200, b'{"private": true, "full_name": "o/r"}')
        self.assertEqual(repo_info("o/r", "tok", opener=opener), {"private": True})

    def test_200_public(self):
        opener, _ = _opener_returning(200, b'{"private": false}')
        self.assertEqual(repo_info("o/r", "tok", opener=opener), {"private": False})

    def test_sends_the_callers_token_as_bearer(self):
        opener, captured = _opener_returning(200, b'{"private": false}')
        repo_info("o/r", "the-token", opener=opener)
        self.assertEqual(captured["req"].get_header("Authorization"), "Bearer the-token")

    def test_404_refuses(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b""))
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_network_error_refuses(self):
        def opener(req, timeout):
            raise urllib.error.URLError("down")
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_garbage_body_refuses(self):
        opener, _ = _opener_returning(200, b"not json")
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_missing_private_field_refuses(self):
        opener, _ = _opener_returning(200, b'{"full_name": "o/r"}')
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_non_bool_private_field_refuses(self):
        opener, _ = _opener_returning(200, b'{"private": "yes"}')
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_no_token_refuses_without_calling_out(self):
        def opener(req, timeout):
            raise AssertionError("must not call out without a token")
        self.assertIsNone(repo_info("o/r", "", opener=opener))


class HeadCommitTests(unittest.TestCase):
    """The staleness probe: what is the repository's default-branch HEAD now?

    Fail-safe like `repo_info`. An unknown HEAD must return None so the caller
    reports "unknown", never "up to date" -- telling someone their index is
    current when we could not check is the same class of failure as a bluffed
    citation.
    """

    def test_returns_the_head_sha(self):
        opener, _ = _opener_returning(200, b'[{"sha": "abc123"}]')
        self.assertEqual(head_commit("o/r", "tok", opener=opener), "abc123")

    def test_sends_the_callers_token_as_bearer(self):
        seen = {}

        def opener(req, timeout):
            seen["auth"] = req.get_header("Authorization")
            return _Resp(200, b'[{"sha": "abc123"}]')
        head_commit("o/r", "tok", opener=opener)
        self.assertEqual(seen["auth"], "Bearer tok")

    def test_asks_for_exactly_one_commit(self):
        seen = {}

        def opener(req, timeout):
            seen["url"] = req.full_url
            return _Resp(200, b'[{"sha": "abc123"}]')
        head_commit("o/r", "tok", opener=opener)
        self.assertIn("per_page=1", seen["url"])

    def test_works_without_a_token_for_a_public_repo(self):
        # Unlike repo_info, which is a permission gate and must refuse without
        # a token, this is a public read -- refusing would make freshness
        # unavailable on the web surface, which signs in with read:user only.
        opener, _ = _opener_returning(200, b'[{"sha": "abc123"}]')
        self.assertEqual(head_commit("o/r", None, opener=opener), "abc123")

    def test_empty_list_is_unknown(self):
        opener, _ = _opener_returning(200, b'[]')
        self.assertIsNone(head_commit("o/r", "tok", opener=opener))

    def test_non_200_is_unknown(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b""))
        self.assertIsNone(head_commit("o/r", "tok", opener=opener))

    def test_network_error_is_unknown(self):
        def opener(req, timeout):
            raise urllib.error.URLError("down")
        self.assertIsNone(head_commit("o/r", "tok", opener=opener))

    def test_garbage_body_is_unknown(self):
        opener, _ = _opener_returning(200, b"not json")
        self.assertIsNone(head_commit("o/r", "tok", opener=opener))

    def test_missing_sha_is_unknown(self):
        opener, _ = _opener_returning(200, b'[{"commit": {}}]')
        self.assertIsNone(head_commit("o/r", "tok", opener=opener))


class CommitsBetweenTests(unittest.TestCase):
    """How far behind, as a real number rather than "different"."""

    def test_returns_ahead_by(self):
        opener, _ = _opener_returning(200, b'{"status": "ahead", "ahead_by": 9}')
        self.assertEqual(commits_between("o/r", "old", "new", "tok", opener=opener), 9)

    def test_identical_is_zero(self):
        opener, _ = _opener_returning(200, b'{"status": "identical", "ahead_by": 0}')
        self.assertEqual(commits_between("o/r", "a", "a", "tok", opener=opener), 0)

    def test_compares_base_to_head_in_that_order(self):
        seen = {}

        def opener(req, timeout):
            seen["url"] = req.full_url
            return _Resp(200, b'{"ahead_by": 1}')
        commits_between("o/r", "base1", "head2", "tok", opener=opener)
        self.assertIn("base1...head2", seen["url"])

    def test_non_integer_count_is_unknown(self):
        opener, _ = _opener_returning(200, b'{"ahead_by": "nine"}')
        self.assertIsNone(commits_between("o/r", "a", "b", "tok", opener=opener))

    def test_missing_count_is_unknown(self):
        opener, _ = _opener_returning(200, b'{"status": "ahead"}')
        self.assertIsNone(commits_between("o/r", "a", "b", "tok", opener=opener))

    def test_network_error_is_unknown(self):
        def opener(req, timeout):
            raise urllib.error.URLError("down")
        self.assertIsNone(commits_between("o/r", "a", "b", "tok", opener=opener))

    def test_missing_arguments_never_call_out(self):
        def opener(req, timeout):
            raise AssertionError("must not call out without both commits")
        self.assertIsNone(commits_between("o/r", "", "b", "tok", opener=opener))
        self.assertIsNone(commits_between("o/r", "a", "", "tok", opener=opener))


if __name__ == "__main__":
    unittest.main()
