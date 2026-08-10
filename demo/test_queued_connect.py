"""The queued ingest: /connect answers immediately and the job is observable.

The failure this fixes, measured live 2026-08-10: connecting astral-sh/uv ran
Stage 1 inside the HTTP request, Azure's fixed 240s ingress timeout killed the
request, and `/status` -- which only reassigns `repo` at the stage-1 publish,
after the whole ingest -- reported the PREVIOUS repo the entire time. A running
job and no job at all were indistinguishable for twenty minutes.

Stdlib only, no network, no model.
"""
import tempfile
import threading
import time
import unittest
from pathlib import Path

from demo.library import Library
from demo.test_library import _seed_corpus


class ConnectingToTests(unittest.TestCase):
    """`connecting_to` is the field that makes an in-flight job visible."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.cache_root = root / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def _library(self, ingest):
        return Library(self.default_dir, self.cache_root, "simonw/llm",
                       build_pipeline=lambda corpus_dir, fast=False, **_: "pipeline",
                       ingest_fn=ingest)

    def test_absent_when_idle(self):
        lib = self._library(lambda *a, **k: None)
        self.assertIsNone(lib.status_snapshot()["connecting_to"])

    def test_names_the_target_repo_while_ingesting(self):
        """The whole point: DURING the slow part, status must say which repo is
        being connected -- `repo` still holds the previous one."""
        seen = {}
        started, release = threading.Event(), threading.Event()

        def slow_ingest(repo, out_dir, **kw):
            seen["snapshot"] = lib.status_snapshot()
            started.set()
            release.wait(5)
            raise RuntimeError("stop here; stage 1 is what we're measuring")

        lib = self._library(slow_ingest)
        t = threading.Thread(target=lib.connect_sync, args=("owner/big",), daemon=True)
        t.start()
        self.assertTrue(started.wait(5))
        snap = seen["snapshot"]
        self.assertEqual(snap["connecting_to"], "owner/big")
        self.assertEqual(snap["state"], "indexing")
        # ...and `repo` is still the OLD one, which is exactly why the new
        # field is needed rather than reading `repo`.
        self.assertNotEqual(snap["repo"], "owner/big")
        release.set()
        t.join(5)

    def test_cleared_after_failure(self):
        """A dead job must not leave status pointing at a repo nothing is
        working on -- that would be a new way to mislead a reader."""
        def failing(repo, out_dir, **kw):
            raise RuntimeError("boom")

        lib = self._library(failing)
        lib.connect_sync("owner/broken")
        snap = lib.status_snapshot()
        self.assertIsNone(snap["connecting_to"])
        self.assertEqual(snap["state"], "error")


class QueuedDispatchTests(unittest.TestCase):
    """What the server actually hands the worker thread, exercised through the
    real handler rather than by reading the source."""

    def _connect(self, **kw):
        from demo.test_server import _StubLibrary, _ServerFixture, _post
        lib = _StubLibrary()
        fx = _ServerFixture(lib, sync_connect=False, **kw)
        try:
            status, payload = _post(fx.base + "/connect", {"repo": "octocat/hello"})
            # 202 returns before the worker runs; wait for the recorded call.
            for _ in range(100):
                if lib.connect_calls:
                    break
                time.sleep(0.02)
            return status, payload, lib
        finally:
            fx.close()

    def test_queued_connect_returns_202_immediately(self):
        status, payload, lib = self._connect()
        self.assertEqual(status, 202)
        self.assertEqual(payload["state"], "indexing")
        self.assertEqual(payload["connecting_to"], "octocat/hello")

    def test_queued_path_passes_background_upgrade(self):
        """RED before this brick: the async branch omitted background_upgrade,
        so a queued connect ran stage 2 INLINE while the sync path backgrounded
        it -- the two routes disagreed about when a repo becomes answerable.
        Proven by reverting the kwarg and watching this fail."""
        status, payload, lib = self._connect(background_upgrade=True)
        self.assertEqual(lib.background_upgrades, [True])

    def test_background_upgrade_off_is_still_honoured(self):
        status, payload, lib = self._connect(background_upgrade=False)
        self.assertEqual(lib.background_upgrades, [False])


if __name__ == "__main__":
    unittest.main()
