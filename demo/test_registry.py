# demo/test_registry.py
"""The registry is the isolation core: one Library per user id, per-user storage,
a shared read-only default pipeline, LRU-bounded memory, and safe disconnect."""

import json
import tempfile
import unittest
from unittest import mock
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

        def fake_build(corpus_dir, fast=False):
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

    def test_public_corpus_lands_in_shared_cache_not_under_user_id(self):
        # A public repo's corpus is shared public data -- it must live in the
        # shared cache, never filed under the connecting user's identity dir
        # (that dir is reserved for per-user/private state).
        a = self.reg.library_for("1001")
        a.connect_sync("octo/xrepo")
        self.assertTrue((self.storage / "public.cache" / "octo__xrepo" / "chunks.jsonl").exists())
        self.assertFalse((self.storage / "1001" / "cache" / "octo__xrepo").exists())
        self.assertFalse((self.storage / "1002").exists())

    def test_public_corpus_is_shared_across_users_one_ingest(self):
        # A public repo's index is a deterministic function of public input, so
        # it must be ingested ONCE and shared, not cloned+embedded privately per
        # user (30 testers connecting the same repo must not = 30 identical jobs).
        ingested = []

        def counting_ingest(repo, out_dir, commit=None, code_dir=".", token=None):
            ingested.append(repo)
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build, ingest_fn=counting_ingest)
        reg.library_for("1001").connect_sync("octo/shared")
        reg.library_for("1002").connect_sync("octo/shared")

        self.assertEqual(ingested, ["octo/shared"])  # ONE ingest, shared by both users
        shared = self.storage / "public.cache" / "octo__shared" / "chunks.jsonl"
        self.assertTrue(shared.exists())
        # No private per-user duplicate of the public corpus.
        self.assertFalse((self.storage / "1001" / "cache" / "octo__shared").exists())
        self.assertFalse((self.storage / "1002" / "cache" / "octo__shared").exists())

    def test_private_repo_lands_in_the_shared_private_root_not_the_public_cache(self):
        # THE load-bearing isolation: a private repo's corpus goes into the
        # caller's OWN identity dir, never the shared public cache, and is cloned
        # with the caller's OWN token.
        ingested = []

        def counting_ingest(repo, out_dir, commit=None, code_dir=".", token=None):
            ingested.append((repo, token))
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build, ingest_fn=counting_ingest)
        snap = reg.library_for("1001").connect_sync("acme/secret", token="ghp_caller", private=True)

        self.assertEqual(snap["private"], True)
        # CHANGED 2026-07-27 (T1): private corpora live in their own SHARED root,
        # readable by everyone GitHub says may read that repo -- never under one
        # person's directory, and never in the public cache.
        self.assertTrue((self.storage / "private.cache" / "acme__secret" / "chunks.jsonl").exists())
        self.assertFalse((self.storage / "public.cache" / "acme__secret").exists())  # never public
        self.assertEqual(ingested, [("acme/secret", "ghp_caller")])  # cloned with the caller's token

    def test_two_users_share_one_private_corpus(self):
        # CHANGED 2026-07-27 (organisation brain, T1). This previously asserted
        # the opposite: the same private repo connected by two people was
        # ingested separately into each person's own storage.
        #
        # That per-user split WAS the isolation -- there was no read-side check,
        # so keeping the corpora apart was the only thing stopping one caller
        # reading another's private code. It is no longer the isolation:
        # demo/server.py now verifies on every read that the caller can read
        # that repo on GitHub (T3, ReadEntitlementTests). With the guard in
        # place, a second identical clone of the same private repo is pure waste
        # -- and it is exactly what stops three engineers at one company from
        # sharing a brain.
        ingested = []

        def counting_ingest(repo, out_dir, commit=None, code_dir=".", token=None):
            ingested.append(repo)
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build, ingest_fn=counting_ingest)
        reg.library_for("1001").connect_sync("acme/secret", token="tokA", private=True)
        reg.library_for("1002").connect_sync("acme/secret", token="tokB", private=True)

        self.assertEqual(ingested, ["acme/secret"], "one ingest, shared -- not one per person")
        shared = self.storage / "private.cache" / "acme__secret" / "chunks.jsonl"
        self.assertTrue(shared.exists())
        # And nothing private is left sitting under an individual's own directory.
        self.assertFalse((self.storage / "1001" / "private").exists())
        self.assertFalse((self.storage / "1002" / "private").exists())

    def test_private_corpus_never_lands_in_the_public_cache(self):
        # Shared-between-entitled-readers is NOT the same as public. Private
        # corpora get their own root, which no unauthenticated path serves.
        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build, ingest_fn=self.reg._ingest_fn)
        reg.library_for("1001").connect_sync("acme/secret", token="tokA", private=True)
        self.assertFalse((self.storage / "public.cache" / "acme__secret").exists())

    def test_disconnect_does_not_delete_the_shared_private_corpus(self):
        # CHANGED 2026-07-27 (organisation brain, D4). This previously asserted
        # that disconnecting deleted the private corpus. Once the corpus is
        # shared, that behaviour would let one person destroy their whole team's
        # brain by tidying up their own account. Disconnect now forgets only the
        # caller's own pointer and record dir.
        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build, ingest_fn=self.reg._ingest_fn)
        reg.library_for("1001").connect_sync("acme/secret", token="tokA", private=True)
        shared = self.storage / "private.cache" / "acme__secret" / "chunks.jsonl"
        self.assertTrue(shared.exists())

        reg.disconnect("1001")

        self.assertFalse((self.storage / "1001").exists())   # their own record dir goes
        self.assertTrue(shared.exists(), "one person leaving must not delete the team's index")

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
                              build_pipeline=lambda d, fast=False: f"p::{d}",
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

    def test_lru_eviction_resume_never_calls_ingest(self):
        # Pinning test: resuming a repo after eviction must always be a cache
        # hit -- ingest_fn is called exactly once, for the ORIGINAL connect,
        # and never again during any later eviction+resume. This is exactly
        # what makes it safe for resume to sit outside the rate limiter's
        # reach (Task 15): if a future change ever made resume re-ingest, it
        # would add unthrottled subprocess/network cost to a path nothing
        # throttles -- this test exists to catch that regression, not just
        # today's correct-by-inspection behavior.
        ingested = []

        def counting_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            ingested.append(repo)
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=self.reg._base_build,
                              ingest_fn=counting_ingest, max_live=2)

        reg.library_for("1").connect_sync("octo/xrepo")
        self.assertEqual(ingested, ["octo/xrepo"])  # the one real ingest

        reg.library_for("2")
        reg.library_for("3")  # evicts "1"
        rebuilt = reg.library_for("1")  # triggers resume -- must be a cache hit

        self.assertEqual(rebuilt.status_snapshot()["repo"], "octo/xrepo")
        self.assertEqual(ingested, ["octo/xrepo"])  # still just the one call

    def test_disconnect_forgets_the_user_but_never_the_shared_corpus(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        a.connect_sync("octo/xrepo")
        b.connect_sync("octo/yrepo")
        shared_x = self.storage / "public.cache" / "octo__xrepo"
        shared_y = self.storage / "public.cache" / "octo__yrepo"
        self.reg.disconnect("1001")
        # A's own identity dir is gone; a fresh library for A resets to default.
        self.assertFalse((self.storage / "1001").exists())
        self.assertEqual(self.reg.library_for("1001").status_snapshot()["repo"], "simonw/llm")
        # B is untouched, and NEITHER shared corpus is deleted -- shared public
        # data is nobody's private data; disconnect must never nuke it.
        self.assertEqual(b.status_snapshot()["repo"], "octo/yrepo")
        self.assertTrue((shared_x / "chunks.jsonl").exists())
        self.assertTrue((shared_y / "chunks.jsonl").exists())

    def test_disconnect_deletes_the_users_own_record_dir_only(self):
        # The per-identity dir <storage>/<id>/ is where per-user/private state
        # lives (today: connection record; future: private-repo corpora).
        # disconnect must delete exactly that, and never the shared public cache.
        (self.storage / "1001").mkdir(parents=True)
        (self.storage / "1001" / "private.txt").write_text("mine")
        pub = self.storage / "public.cache" / "octo__pub"
        pub.mkdir(parents=True)
        (pub / "chunks.jsonl").write_text("{}\n")
        self.reg.disconnect("1001")
        self.assertFalse((self.storage / "1001").exists())     # the user's own data: gone
        self.assertTrue((pub / "chunks.jsonl").exists())        # shared public data: untouched

    def test_disconnect_surfaces_delete_failure(self):
        def fail_unless_ignored(path, ignore_errors=False):
            if not ignore_errors:
                raise PermissionError("denied")

        with mock.patch("demo.registry.shutil.rmtree", fail_unless_ignored):
            with self.assertRaises(PermissionError):
                self.reg.disconnect("1001")


if __name__ == "__main__":
    unittest.main()
