# demo/test_library.py
"""The Library holds the active pipeline + status and switches repos: cache-hit
is instant, a miss ingests into a git-ignored cache, errors keep the old repo."""

import json
import tempfile
import unittest
from pathlib import Path

from evals.corpus_meta import write_meta
from .library import Library


def _seed_corpus(dir_, repo, commit="c0ffee"):
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "chunks.jsonl").write_text(json.dumps({"ref": "pr:1", "source": "pr", "text": "why"}) + "\n")
    write_meta(d / "meta.json", repo=repo, commit=commit, code_dir=".", counts={"pr": 1, "issue": 0, "code": 0})


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.cache_root = root / "cache"
        self.built = []  # dirs build_pipeline was called with
        self.ingested = []  # repos ingest_fn was called with

        def fake_build(corpus_dir, fast=False):
            self.built.append(str(corpus_dir))
            return f"pipeline::{corpus_dir}"

        self.ingest_code_dirs = []

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            self.ingested.append(repo)
            self.ingest_code_dirs.append(code_dir)
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                           build_pipeline=fake_build, ingest_fn=fake_ingest)

    def tearDown(self):
        self.tmp.cleanup()

    def test_starts_on_default_repo(self):
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertEqual(s["repo"], "simonw/llm")
        self.assertEqual(self.lib.current_pipeline(), f"pipeline::{self.default_dir}")

    def test_connect_uncached_ingests_then_switches(self):
        self.lib.connect_sync("octo/new")
        self.assertEqual(self.ingested, ["octo/new"])
        self.assertEqual(self.ingest_code_dirs, ["."])  # whole repo, not simonw/llm's `llm/`
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertEqual(s["repo"], "octo/new")

    def test_cache_hit_does_not_reingest(self):
        _seed_corpus(self.cache_root / "octo__cached", "octo/cached")
        self.lib.connect_sync("octo/cached")
        self.assertEqual(self.ingested, [])  # never ingested
        self.assertEqual(self.lib.status_snapshot()["repo"], "octo/cached")

    def test_default_repo_uses_committed_corpus(self):
        self.lib.connect_sync("octo/new")  # move away
        self.lib.connect_sync("simonw/llm")  # back
        self.assertEqual(self.ingested, ["octo/new"])  # default never ingested
        self.assertEqual(self.lib.status_snapshot()["repo"], "simonw/llm")

    def test_ingest_failure_keeps_previous_repo(self):
        def boom(repo, out_dir, commit=None, code_dir="llm", token=None):
            raise RuntimeError("gh exploded")
        self.lib._ingest_fn = boom
        self.lib.connect_sync("bad/repo")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertEqual(s["repo"], "simonw/llm")  # still on the old repo
        self.assertEqual(self.lib.current_pipeline(), f"pipeline::{self.default_dir}")

    def test_ingest_failure_reports_generic_error(self):
        # The raw exception (command lines, URLs) must never reach /status.
        def boom(repo, out_dir, commit=None, code_dir="llm", token=None):
            raise RuntimeError("git clone https://github.com/o/r.git failed: fatal ...")
        self.lib._ingest_fn = boom
        self.lib.connect_sync("o/r")
        err = self.lib.status_snapshot()["error"]
        self.assertNotIn("github.com", err)
        self.assertNotIn("git clone", err)
        self.assertIn("index", err.lower())

    def test_connect_publishes_the_fast_pipeline_before_the_full_one(self):
        # STAGE 1 (fast, lexical-only) must land first; STAGE 2 (full/hybrid)
        # upgrades it. Proves both stages actually run, in the right order,
        # for a real (non-slow, non-failing) connect.
        calls = []

        def build(corpus_dir, fast=False):
            calls.append(fast)
            return f"fast::{corpus_dir}" if fast else f"full::{corpus_dir}"

        self.lib._build_pipeline = build
        self.lib.connect_sync("octo/new")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertEqual(s["repo"], "octo/new")
        self.assertTrue(self.lib.current_pipeline().startswith("full::"))  # upgraded
        self.assertEqual(calls, [True, False])  # fast, then full -- in that order

    def test_background_upgrade_returns_after_stage1_and_upgrades_in_background(self):
        # Option B: connect_sync(background_upgrade=True) must return the moment
        # STAGE 1 (lexical) is ready, running STAGE 2 (the embed) on a daemon
        # thread -- so an HTTP request is never held through the multi-minute
        # embed (and can't hit a platform ingress timeout). The full pipeline
        # still swaps in once the background embed finishes.
        import threading
        import time
        gate = threading.Event()

        def build(corpus_dir, fast=False):
            if fast:
                return f"fast::{corpus_dir}"
            gate.wait(timeout=2)          # hold STAGE 2 open
            return f"full::{corpus_dir}"

        self.lib._build_pipeline = build
        s = self.lib.connect_sync("octo/bg", background_upgrade=True)
        # Returned already, on the fast pipeline, before STAGE 2 could finish:
        self.assertEqual(s["state"], "ready")
        self.assertTrue(self.lib.current_pipeline().startswith("fast::"))
        # STAGE 2 finishes in the background and swaps in the full pipeline:
        gate.set()
        for _ in range(200):
            if self.lib.current_pipeline().startswith("full::"):
                break
            time.sleep(0.01)
        self.assertTrue(self.lib.current_pipeline().startswith("full::"))
        self.assertEqual(self.lib.status_snapshot()["state"], "ready")

    def test_stale_semantic_upgrade_does_not_clobber_a_newer_reconnect(self):
        # P1 (found by an independent GPT-5.6 review): under Option B, connect_sync
        # returns while stage 2 runs in the background, so two connects to the SAME
        # repo overlap. A stale stage 2 from the FIRST connect must NOT overwrite
        # the newer connect's pipeline -- the generation guard (not the repo name)
        # is what prevents the lost update.
        import threading
        import time
        hold_first = threading.Event()
        full_calls = []
        clock = threading.Lock()

        def build(corpus_dir, fast=False):
            if fast:
                return f"fast::{corpus_dir}"
            with clock:
                full_calls.append(corpus_dir)
                n = len(full_calls)
            if n == 1:                       # the FIRST (older-generation) build blocks
                hold_first.wait(timeout=3)
                return "full::gen1"
            return f"full::gen{n}"           # later builds finish immediately

        self.lib._build_pipeline = build
        # 1) First connect (bg): stage 1 lands; stage-2 gen1 build blocks.
        self.lib.connect_sync("octo/a", background_upgrade=True)
        for _ in range(300):                 # wait until the gen1 build is holding the gate
            if full_calls:
                break
            time.sleep(0.01)
        # 2) Reconnect the SAME repo (bg): stage-2 gen2 builds fast and installs.
        self.lib.connect_sync("octo/a", background_upgrade=True)
        for _ in range(300):
            if self.lib.current_pipeline() == "full::gen2":
                break
            time.sleep(0.01)
        self.assertEqual(self.lib.current_pipeline(), "full::gen2")  # newer is live
        # 3) Release the stale gen1 build; it must NOT clobber gen2.
        hold_first.set()
        for _ in range(50):
            time.sleep(0.01)
        self.assertEqual(self.lib.current_pipeline(), "full::gen2")  # stale gen1 refused

    def test_slow_or_failed_semantic_upgrade_does_not_undo_a_working_connect(self):
        # A TimeoutError from STAGE 2 (e.g. SemanticRetriever's embed-timeout,
        # see evals/retriever.py -- proven live on a CPU-throttled host: a
        # 216-chunk connect never finished embedding inside a 15-minute bound)
        # must NOT undo STAGE 1's already-working connection. The repo stays
        # "ready" via lexical-only search, not "error".
        def build(corpus_dir, fast=False):
            if fast:
                return f"fast::{corpus_dir}"
            raise TimeoutError("embedding timed out after 900s (10/216 chunks done)")

        self.lib._build_pipeline = build
        self.lib.connect_sync("octo/big")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")  # NOT "error" -- stage 1 already succeeded
        self.assertEqual(s["repo"], "octo/big")
        self.assertTrue(self.lib.current_pipeline().startswith("fast::"))  # stayed lexical-only

    def test_stage_two_completion_does_not_clobber_a_meanwhile_repo_switch(self):
        # If the caller switches to a DIFFERENT repo while an earlier repo's
        # slow stage 2 is still running (a real race: /connect backgrounds
        # each call on its own thread, so two different repos' connect_sync
        # calls can genuinely overlap), the late-finishing stage 2 must not
        # clobber the repo the caller actually switched to.
        import threading
        import time

        gate = threading.Event()

        def build(corpus_dir, fast=False):
            if not fast and "first" in str(corpus_dir):
                gate.wait(timeout=2)  # hold octo/first's stage 2 open
            return f"{'fast' if fast else 'full'}::{corpus_dir}"

        self.lib._build_pipeline = build
        t = threading.Thread(target=self.lib.connect_sync, args=("octo/first",))
        t.start()
        for _ in range(100):  # wait for octo/first's stage 1 to land
            if self.lib.status_snapshot()["repo"] == "octo/first":
                break
            time.sleep(0.02)
        else:
            self.fail("octo/first's stage 1 never became ready")

        self.lib.connect_sync("octo/second")  # switches away; runs both stages fully
        gate.set()  # now let octo/first's blocked stage 2 finish
        t.join(timeout=2)

        s = self.lib.status_snapshot()
        self.assertEqual(s["repo"], "octo/second")
        self.assertIn("octo__second", self.lib.current_pipeline())
        self.assertTrue(self.lib.current_pipeline().startswith("full::"))

    def test_reconnect_not_blocked_by_a_prior_pending_semantic_upgrade(self):
        # P1 regression (docs/HANDOFF.md §6): the single-flight slot (_inflight)
        # must be released after STAGE 1, not held for the whole two-stage call.
        # Otherwise a reconnect to a repo whose earlier STAGE 2 (semantic
        # upgrade) is still running hits the `already_indexing` guard and is
        # silently swallowed -- connect_sync returns a DIFFERENT repo's status
        # and nothing ever restarts the real connect, so a client polling for
        # the reconnected repo waits forever.
        import threading
        import time

        gate = threading.Event()

        def build(corpus_dir, fast=False):
            # Hold octo/first's STAGE 2 open; every other build is instant.
            if not fast and "first" in str(corpus_dir):
                gate.wait(timeout=5)
            return f"{'fast' if fast else 'full'}::{corpus_dir}"

        self.lib._build_pipeline = build

        def wait_for_repo(repo, timeout=2.0):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.lib.status_snapshot()["repo"] == repo:
                    return True
                time.sleep(0.02)
            return False

        # 1) Connect octo/first: stage 1 lands, stage 2 blocks on the gate.
        t1 = threading.Thread(target=self.lib.connect_sync, args=("octo/first",))
        t1.start()
        self.assertTrue(wait_for_repo("octo/first"), "octo/first stage 1 never landed")

        # 2) Switch to octo/second (a different repo -- completes fully).
        self.lib.connect_sync("octo/second")
        self.assertEqual(self.lib.status_snapshot()["repo"], "octo/second")

        # 3) Reconnect octo/first while its ORIGINAL stage 2 is STILL blocked.
        t2 = threading.Thread(target=self.lib.connect_sync, args=("octo/first",))
        t2.start()
        try:
            switched_back = wait_for_repo("octo/first", timeout=2.0)
        finally:
            gate.set()  # release both blocked stage-2 embeds
            t1.join(timeout=5)
            t2.join(timeout=5)

        self.assertTrue(
            switched_back,
            "reconnect was swallowed by the pending semantic upgrade; "
            "repo never returned to octo/first",
        )

    def test_concurrent_connect_to_same_repo_ingests_once(self):
        import threading
        import time
        gate = threading.Event()
        started = []

        def slow_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            started.append(repo)
            gate.wait(timeout=2)
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.lib._ingest_fn = slow_ingest
        t1 = threading.Thread(target=self.lib.connect_sync, args=("o/r",))
        t2 = threading.Thread(target=self.lib.connect_sync, args=("o/r",))
        t1.start()
        time.sleep(0.1)  # let the first take the in-flight slot
        t2.start()
        time.sleep(0.1)
        gate.set()
        t1.join(); t2.join()
        self.assertEqual(started.count("o/r"), 1)  # single-flight: one ingest only


class PrivateConnectTests(unittest.TestCase):
    """Private repos use their own storage, their own pipeline builder, and are
    refused up-front (never touching ingest) when the paid writer isn't ready."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.cache_root = root / "cache"
        self.built = []          # (corpus_dir,) build_pipeline was called with
        self.private_built = []  # (corpus_dir,) build_private_pipeline was called with
        self.ingested = []       # (repo, token) ingest_fn was called with

        def fake_build(corpus_dir, fast=False):
            self.built.append(str(corpus_dir))
            return f"pipeline::{corpus_dir}"

        def fake_private_build(corpus_dir, fast=False):
            self.private_built.append(str(corpus_dir))
            return f"private-pipeline::{corpus_dir}"

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            self.ingested.append((repo, token))
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.fake_ingest = fake_ingest
        self.lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                           build_pipeline=fake_build, ingest_fn=fake_ingest,
                           build_private_pipeline=fake_private_build,
                           private_ready=lambda: True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_private_connect_uses_private_storage_and_pipeline(self):
        self.lib.connect_sync("acme/secret", token="tok-123", private=True)
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertEqual(s["repo"], "acme/secret")
        self.assertTrue(s["private"])
        self.assertEqual(self.ingested, [("acme/secret", "tok-123")])
        # Private storage is a sibling of the public cache root, not inside it.
        private_dir = self.cache_root.parent / "private" / "acme__secret"
        self.assertTrue((private_dir / "chunks.jsonl").exists())
        self.assertFalse((self.cache_root / "acme__secret").exists())
        # Called twice: STAGE 1 (fast, lexical-only) then STAGE 2 (the
        # upgrade) -- both against the same private corpus dir.
        self.assertEqual(self.private_built, [str(private_dir), str(private_dir)])
        # The public builder was only used once, at construction (for the
        # default repo) -- never for this private connect.
        self.assertEqual(self.built, [str(self.default_dir)])

    def test_public_connect_is_unaffected(self):
        self.lib.connect_sync("octo/new")
        s = self.lib.status_snapshot()
        self.assertFalse(s["private"])
        self.assertEqual(self.ingested, [("octo/new", None)])  # no token spent
        self.assertEqual(self.private_built, [])  # the private builder was never used

    def test_private_not_ready_refuses_before_any_ingest(self):
        lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                     build_pipeline=lambda d: f"pipeline::{d}",
                     ingest_fn=self.fake_ingest,
                     build_private_pipeline=lambda d: f"private::{d}",
                     private_ready=lambda: False)
        lib.connect_sync("acme/secret", token="tok-secret", private=True)
        s = lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertEqual(self.ingested, [])  # never even attempted
        self.assertNotIn("tok-secret", s["error"])
        # Still on the original default repo -- nothing was switched.
        self.assertEqual(s["repo"], "simonw/llm")

    def test_token_never_appears_in_status_snapshot(self):
        caller_token = "tok-shh-999"
        self.lib.connect_sync("acme/secret", token=caller_token, private=True)
        s = self.lib.status_snapshot()
        self.assertNotIn(caller_token, json.dumps(s))

    def test_interlock_refusal_inside_connect_sync_leaves_state_untouched(self):
        # The trust interlock is unit-tested in isolation (evals/test_trust.py)
        # and exercised via a fake build_private_pipeline in the other tests
        # above -- but nothing proves what happens when it actually RAISES
        # from inside connect_sync's try block (the same composition the real
        # _default_build_private_pipeline uses: assert_safe_for_private then
        # GatedPipeline construction). It must be caught by the same generic
        # except-and-report-error path as any other build/ingest failure,
        # leaving whatever was connected before completely untouched -- never
        # a partially-applied repo/private flag/pipeline.
        from evals.trust import PrivateDataError

        def raising_private_build(corpus_dir, fast=False):
            raise PrivateDataError("not private-safe: refusing to send private code")

        lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                     build_pipeline=lambda d, fast=False: f"pipeline::{d}",
                     ingest_fn=self.fake_ingest,
                     build_private_pipeline=raising_private_build,
                     private_ready=lambda: True)

        # A known-good baseline: a successful public connect first.
        lib.connect_sync("octo/known-good")
        baseline_pipeline = lib.current_pipeline()
        baseline_provenance = lib.provenance()

        # The interlock refuses mid-construction on this private attempt.
        lib.connect_sync("acme/secret", token="tok-danger", private=True)

        s = lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertEqual(s["error"],
                         "Couldn't index that repo. Check it's a public owner/name and try again.")
        self.assertNotIn("PrivateDataError", s["error"])
        self.assertNotIn("tok-danger", s["error"])
        # Everything from before the refused attempt is untouched -- not the
        # refused repo, not flipped to private, not a half-built pipeline.
        self.assertEqual(s["repo"], "octo/known-good")
        self.assertFalse(s["private"])
        self.assertEqual(lib.current_pipeline(), baseline_pipeline)
        self.assertEqual(lib.provenance(), baseline_provenance)


if __name__ == "__main__":
    unittest.main()
