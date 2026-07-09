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

        def fake_build(corpus_dir):
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

    def test_embed_timeout_reports_distinct_honest_message(self):
        # A TimeoutError (e.g. from SemanticRetriever's embed-timeout, see
        # evals/retriever.py) is NOT a bad-repo error -- the repo is fine, the
        # server is just too slow right now. Must not reuse the generic
        # "public owner/name" message, which would mislead the caller into
        # thinking the repo itself is the problem.
        def slow_build(corpus_dir):
            raise TimeoutError("embedding timed out after 900s (10/216 chunks done)")
        self.lib._build_pipeline = slow_build
        self.lib.connect_sync("octo/big")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertIn("too long", s["error"].lower())
        self.assertNotIn("public owner/name", s["error"])
        self.assertEqual(s["repo"], "simonw/llm")  # stayed on the old repo

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

        def fake_build(corpus_dir):
            self.built.append(str(corpus_dir))
            return f"pipeline::{corpus_dir}"

        def fake_private_build(corpus_dir):
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
        self.assertEqual(self.private_built, [str(private_dir)])
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

        def raising_private_build(corpus_dir):
            raise PrivateDataError("not private-safe: refusing to send private code")

        lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                     build_pipeline=lambda d: f"pipeline::{d}",
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
