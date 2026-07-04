# demo/test_registry.py
"""The registry is the isolation core: one Library per user id, per-user storage,
a shared read-only default pipeline, LRU-bounded memory, and safe disconnect."""

import json
import tempfile
import unittest
from pathlib import Path

from evals.corpus_meta import write_meta
from .registry import LibraryRegistry


def _seed_corpus(dir_, repo, commit="c0ffee"):
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "chunks.jsonl").write_text(json.dumps({"ref": "pr:1", "source": "pr", "text": "why"}) + "\n")
    write_meta(d / "meta.json", repo=repo, commit=commit, code_dir=".", counts={"pr": 1, "issue": 0, "code": 0})


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.storage = root / "storage"
        self.builds = []

        def fake_build(corpus_dir):
            self.builds.append(str(corpus_dir))
            return f"pipeline::{corpus_dir}"

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                                   build_pipeline=fake_build, ingest_fn=fake_ingest)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_user_gets_the_same_library(self):
        self.assertIs(self.reg.library_for("1001"), self.reg.library_for("1001"))

    def test_different_users_get_different_libraries(self):
        self.assertIsNot(self.reg.library_for("1001"), self.reg.library_for("1002"))

    def test_users_get_per_user_storage_paths(self):
        a = self.reg.library_for("1001")
        a.connect_sync("octo/xrepo")
        cached = self.storage / "1001" / "cache" / "octo__xrepo" / "chunks.jsonl"
        self.assertTrue(cached.exists())
        self.assertFalse((self.storage / "1002").exists())

    def test_one_users_connect_never_touches_anothers_state(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        a.connect_sync("octo/xrepo")
        self.assertEqual(a.status_snapshot()["repo"], "octo/xrepo")
        self.assertEqual(b.status_snapshot()["repo"], "simonw/llm")

    def test_default_pipeline_is_built_once_and_shared(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        self.assertIs(a.current_pipeline(), b.current_pipeline())
        self.assertEqual(self.builds.count(str(self.default_dir)), 1)

    def test_anonymous_maps_to_one_shared_default_view(self):
        self.assertIs(self.reg.library_for(None), self.reg.library_for(None))

    def test_anonymous_is_isolated_from_real_users(self):
        # The identity 'None' case Task 2's review flagged: an unauthenticated
        # caller must get a safe, isolated view -- never another user's library.
        anon = self.reg.library_for(None)
        user = self.reg.library_for("1001")
        user.connect_sync("octo/xrepo")
        self.assertIsNot(anon, user)
        self.assertEqual(anon.status_snapshot()["repo"], "simonw/llm")  # untouched by user's connect

    def test_hostile_user_id_is_rejected(self):
        for bad in ("../../etc", "a/b", "", "x" * 65):
            with self.assertRaises(ValueError):
                self.reg.library_for(bad)

    def test_lru_evicts_idle_libraries(self):
        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=lambda d: f"p::{d}",
                              ingest_fn=lambda *a, **k: None, max_live=2)
        first = reg.library_for("1")
        reg.library_for("2")
        reg.library_for("3")  # evicts "1"
        self.assertIsNot(reg.library_for("1"), first)  # rebuilt, disk cache intact

    def test_lru_eviction_does_not_silently_revert_a_connected_repo(self):
        # Regression: a rebuilt Library must resume the user's own connected
        # repo, not silently fall back to the shared default (Library.__init__
        # always starts on default_repo's meta.json; only the registry knows
        # a per-user cache_root may already hold a different repo on disk).
        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build,
                              ingest_fn=self.reg._ingest_fn, max_live=2)
        reg.library_for("1").connect_sync("octo/xrepo")
        reg.library_for("2")
        reg.library_for("3")  # evicts "1"
        rebuilt = reg.library_for("1")
        self.assertEqual(rebuilt.status_snapshot()["repo"], "octo/xrepo")

    def test_eviction_and_last_repo_write_are_atomic_under_a_racing_request(self):
        # Regression for the eviction/resume race: the evicted key's pop from
        # _libraries and the write to _last_repo must happen under the SAME
        # hold of the registry lock, so a same-key library_for() racing in
        # right as eviction happens can never observe "popped but not yet
        # recorded" and silently rebuild on the default repo instead of
        # resuming.
        #
        # This is deterministic (lock-forced), not a timing/sleep race, so
        # it isn't flaky: the hook below fires from INSIDE the registry's
        # `with self._lock:` block during eviction (status_snapshot() is
        # only called there, right after the pop). It starts the racer
        # thread right then -- the racer immediately blocks trying to
        # acquire self._lock, since the main thread still holds it -- and
        # only lets the racer proceed once the main thread's library_for()
        # call has fully returned (and so released the lock). If the pop
        # and the _last_repo write are atomic under one lock hold (the fix),
        # the racer can only ever see the post-write state. If they were
        # split across two lock holds (the bug), the racer could win the
        # lock in the gap and see "popped, not yet recorded".
        import threading

        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build,
                              ingest_fn=self.reg._ingest_fn, max_live=2)
        reg.library_for("1").connect_sync("octo/xrepo")
        reg.library_for("2")

        from .library import Library
        real_snapshot = Library.status_snapshot
        entered = threading.Event()
        racer_started = threading.Event()
        racer = {}

        def snooping_snapshot(self_lib):
            entered.set()
            t = threading.Thread(target=lambda: racer.update(
                lib=reg.library_for("1")))
            t.start()
            racer["thread"] = t
            racer_started.set()
            return real_snapshot(self_lib)

        Library.status_snapshot = snooping_snapshot
        try:
            reg.library_for("3")  # evicts "1" -- triggers snooping_snapshot
        finally:
            Library.status_snapshot = real_snapshot

        self.assertTrue(entered.is_set())
        self.assertTrue(racer_started.wait(timeout=5))
        racer["thread"].join(timeout=5)
        self.assertFalse(racer["thread"].is_alive())  # actually finished, didn't hang
        self.assertIn("lib", racer)
        self.assertEqual(racer["lib"].status_snapshot()["repo"], "octo/xrepo")

    def test_disconnect_deletes_only_that_users_storage(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        a.connect_sync("octo/xrepo")
        b.connect_sync("octo/yrepo")
        self.reg.disconnect("1001")
        self.assertFalse((self.storage / "1001").exists())
        self.assertTrue((self.storage / "1002" / "cache" / "octo__yrepo").exists())
        # A fresh library for 1001 starts back on the default.
        self.assertEqual(self.reg.library_for("1001").status_snapshot()["repo"], "simonw/llm")


if __name__ == "__main__":
    unittest.main()
