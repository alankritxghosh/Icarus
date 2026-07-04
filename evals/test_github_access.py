# evals/test_github_access.py
"""The private-repo permission gate: GET /repos/{owner}/{repo} AS THE CALLER.
200 -> {"private": bool}; anything else -> None (fail-safe refuse). Offline:
the opener is injected."""

import io
import json
import unittest
import urllib.error

from .github_access import repo_info


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

    def test_no_token_refuses_without_calling_out(self):
        def opener(req, timeout):
            raise AssertionError("must not call out without a token")
        self.assertIsNone(repo_info("o/r", "", opener=opener))


if __name__ == "__main__":
    unittest.main()
