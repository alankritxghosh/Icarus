# demo/test_isolation.py
"""Cross-user isolation, proven at the HTTP boundary (Brick E / Task 13).

Every prior task tested one layer in isolation (registry alone, server alone
against a stub library). This suite is the first to wire a REAL LibraryRegistry
behind a REAL running HTTP server with TWO distinct authenticated identities,
and prove -- by driving actual HTTP requests as each user -- that user A can
never observe or affect user B's connected repo, corpus, storage, or answers.

The fake `build_pipeline`/`ingest_fn` mirror test_registry.py's exact fixture
style, but the fake pipeline answers for real (via the genuine Result/Pipeline
contract from evals/pipeline.py) with prose that bakes in the corpus_dir it was
built from -- so an /ask response's body is a strong, checkable signal of
*which* repo answered, not just a status-field label.
"""

import json
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from evals.corpus_meta import write_meta
from evals.pipeline import Pipeline, Result

from .auth import StaticTokenVerifier
from .registry import LibraryRegistry
from .server import make_handler


def _seed_corpus(dir_, repo, commit="c0ffee"):
    """Mirrors demo/test_registry.py's _seed_corpus fixture exactly."""
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "chunks.jsonl").write_text(
        json.dumps({"ref": "pr:1", "source": "pr", "text": "why"}) + "\n"
    )
    write_meta(d / "meta.json", repo=repo, commit=commit, code_dir=".",
               counts={"pr": 1, "issue": 0, "code": 0})


class _RevealingPipeline(Pipeline):
    """A fake Pipeline whose answer PROVES which corpus_dir it was built from --
    every answer's prose contains the corpus_dir path verbatim, so a test can
    assert (or refute) that a given repo's content appears in an HTTP response
    body without any mocking of the thing under test (the real HTTP path)."""

    def __init__(self, corpus_dir):
        self._corpus_dir = str(corpus_dir)

    def answer(self, question: str) -> Result:
        return Result(
            verdict="answer",
            answer=f"info about {self._corpus_dir}",
            citations=["pr:1"],
            retrieved=["pr:1"],
        )


class _ServerFixture:
    """Spin up a real HTTPServer on a random port over a REAL LibraryRegistry,
    mirroring demo/test_server.py's _ServerFixture pattern (that class takes a
    lib/stub-registry; this one is built to take a real LibraryRegistry, which
    is the new composition this task requires -- test_server.py is untouched)."""

    def __init__(self, registry, **handler_kwargs):
        self._tmp = tempfile.TemporaryDirectory()
        html = Path(self._tmp.name) / "index.html"
        html.write_text("<html></html>")
        handler = make_handler(registry, str(html), **handler_kwargs)
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_port
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()


def _headers(token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _ask(base, token, question):
    data = json.dumps({"question": question}).encode()
    req = urllib.request.Request(base + "/ask", data=data, headers=_headers(token))
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def _status(base, token):
    req = urllib.request.Request(base + "/status", headers=_headers(token))
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def _connect(base, token, repo):
    data = json.dumps({"repo": repo}).encode()
    req = urllib.request.Request(base + "/connect", data=data, headers=_headers(token))
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def _disconnect(base, token):
    req = urllib.request.Request(base + "/disconnect", data=b"{}", headers=_headers(token))
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def _wait_until_ready(base, token, timeout_iters=100):
    """Bounded poll for /status to leave 'indexing' -- mirrors the polling
    pattern already used in demo/test_server.py's test_connect_valid_repo_
    starts_switch (there it polls a stub's `connected` list directly since it
    has no real Library; here we have a real Library so we poll the real
    status_snapshot state machine, which is the stronger, real signal)."""
    import time
    status = None
    for _ in range(timeout_iters):
        _, status = _status(base, token)
        if status["state"] != "indexing":
            return status
        time.sleep(0.02)
    return status


class _IsolationTestBase(unittest.TestCase):
    """Common two-user fixture: a real LibraryRegistry with fake, offline,
    fast build_pipeline/ingest_fn (test_registry.py's exact style) behind a
    real server with require_auth=True and two fake identities."""

    DEFAULT_REPO = "simonw/llm"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, self.DEFAULT_REPO, "94769b8")
        self.storage = root / "storage"

        def fake_build(corpus_dir, fast=False):
            return _RevealingPipeline(corpus_dir)

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.registry = LibraryRegistry(
            self.default_dir, self.storage, self.DEFAULT_REPO,
            build_pipeline=fake_build, ingest_fn=fake_ingest,
        )
        verifier = StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"})
        self.fx = _ServerFixture(self.registry, require_auth=True, verifier=verifier)
        self.base = self.fx.base
        self.TOK_A, self.USER_A = "tok-a", "1001"
        self.TOK_B, self.USER_B = "tok-b", "1002"

        # /connect's caller-scoped GitHub access check (evals.github_access.
        # repo_info) is a real network call against real GitHub tokens -- that
        # gate is already proven in demo/test_server.py's
        # PrivateConnectRouteTests. This suite's job is registry/storage/HTTP
        # isolation given a caller who's ALREADY been let through that gate, so
        # (exactly like those tests) fake it to a clean "public repo" answer
        # rather than depending on network access or real GitHub tokens.
        patcher = unittest.mock.patch(
            "demo.server.github_access.repo_info", return_value={"private": False})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.fx.close()
        self.tmp.cleanup()


class ConnectIsolationTests(_IsolationTestBase):
    """Scenario 1: connecting a repo as A must never be visible to B."""

    def test_b_status_shows_default_after_a_connects(self):
        status, _ = _connect(self.base, self.TOK_A, "octo/xrepo")
        self.assertEqual(status, 202)
        a_status = _wait_until_ready(self.base, self.TOK_A)
        self.assertEqual(a_status["state"], "ready")
        self.assertEqual(a_status["repo"], "octo/xrepo")

        _, b_status = _status(self.base, self.TOK_B)
        self.assertEqual(b_status["repo"], self.DEFAULT_REPO)
        self.assertNotEqual(b_status["repo"], "octo/xrepo")
        # Strongest available signal: the whole JSON body, not just one field.
        self.assertNotIn("octo/xrepo", json.dumps(b_status))


class AskIsolationTests(_IsolationTestBase):
    """Scenario 2: /ask content is tied to each user's own connected repo."""

    def test_a_ask_reveals_xrepo_b_ask_reveals_default_only(self):
        _connect(self.base, self.TOK_A, "octo/xrepo")
        _wait_until_ready(self.base, self.TOK_A)

        status, a_payload = _ask(self.base, self.TOK_A, "why?")
        self.assertEqual(status, 200)
        self.assertIn("octo__xrepo", a_payload["answer"])  # cache dir slug for octo/xrepo

        status, b_payload = _ask(self.base, self.TOK_B, "why?")
        self.assertEqual(status, 200)
        self.assertNotIn("octo__xrepo", b_payload["answer"])
        self.assertNotIn("octo/xrepo", json.dumps(b_payload))
        self.assertIn(str(self.default_dir), b_payload["answer"])


class StorageIsolationTests(_IsolationTestBase):
    """Scenario 3: on-disk storage footprints never cross users."""

    def test_a_has_storage_b_has_none_until_b_acts(self):
        _connect(self.base, self.TOK_A, "octo/xrepo")
        _wait_until_ready(self.base, self.TOK_A)

        a_cache = self.storage / self.USER_A / "cache" / "octo__xrepo" / "chunks.jsonl"
        self.assertTrue(a_cache.exists())
        # B has never made any request that resolves their identity into a
        # Library -- library_for() is what creates storage on disk (via
        # Library's cache_root), and B has issued nothing yet in this test.
        self.assertFalse((self.storage / self.USER_B).exists())


class UnauthenticatedIsolationTests(_IsolationTestBase):
    """Scenario 4: no identity, no state -- an unauthenticated /status is the
    shared anonymous default view; unauthenticated /ask and /connect are 401."""

    def test_unauthenticated_status_shows_shared_default_only(self):
        _connect(self.base, self.TOK_A, "octo/xrepo")
        _wait_until_ready(self.base, self.TOK_A)
        _connect(self.base, self.TOK_B, "octo/yrepo")
        _wait_until_ready(self.base, self.TOK_B)

        status, anon_status = _status(self.base, token=None)
        self.assertEqual(status, 200)
        self.assertEqual(anon_status["repo"], self.DEFAULT_REPO)
        body = json.dumps(anon_status)
        self.assertNotIn("octo/xrepo", body)
        self.assertNotIn("octo/yrepo", body)

    def test_unauthenticated_ask_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _ask(self.base, token=None, question="why?")
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()

    def test_unauthenticated_connect_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _connect(self.base, token=None, repo="octo/xrepo")
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()


class DisconnectIsolationTests(_IsolationTestBase):
    """Scenario 5: A's disconnect only ever touches A's state and storage."""

    def test_a_disconnect_never_affects_b(self):
        _connect(self.base, self.TOK_A, "octo/xrepo")
        _wait_until_ready(self.base, self.TOK_A)
        _connect(self.base, self.TOK_B, "octo/yrepo")
        _wait_until_ready(self.base, self.TOK_B)

        a_cache_dir = self.storage / self.USER_A / "cache" / "octo__xrepo"
        b_cache_dir = self.storage / self.USER_B / "cache" / "octo__yrepo"
        self.assertTrue(a_cache_dir.exists())
        self.assertTrue(b_cache_dir.exists())

        status, _ = _disconnect(self.base, self.TOK_A)
        self.assertEqual(status, 200)

        _, a_status = _status(self.base, self.TOK_A)
        self.assertEqual(a_status["repo"], self.DEFAULT_REPO)

        _, b_status = _status(self.base, self.TOK_B)
        self.assertEqual(b_status["repo"], "octo/yrepo")
        self.assertEqual(b_status["state"], "ready")

        self.assertFalse((self.storage / self.USER_A).exists())
        self.assertTrue(b_cache_dir.exists())


class ProvenanceIsolationTests(_IsolationTestBase):
    """Scenario 6: two DIFFERENT non-default repos -- neither user's answer
    payload ever contains the other's repo name or content anywhere in the
    response body."""

    def test_two_different_repos_never_leak_into_each_other(self):
        _connect(self.base, self.TOK_A, "octo/xrepo")
        _wait_until_ready(self.base, self.TOK_A)
        _connect(self.base, self.TOK_B, "octo/yrepo")
        _wait_until_ready(self.base, self.TOK_B)

        status, a_payload = _ask(self.base, self.TOK_A, "why?")
        self.assertEqual(status, 200)
        status, b_payload = _ask(self.base, self.TOK_B, "why?")
        self.assertEqual(status, 200)

        a_body, b_body = json.dumps(a_payload), json.dumps(b_payload)
        self.assertIn("octo__xrepo", a_body)
        self.assertIn("octo__yrepo", b_body)
        # Neither user's full response body ever mentions the other's repo.
        self.assertNotIn("yrepo", a_body)
        self.assertNotIn("octo/yrepo", a_body)
        self.assertNotIn("xrepo", b_body)
        self.assertNotIn("octo/xrepo", b_body)


if __name__ == "__main__":
    unittest.main()
