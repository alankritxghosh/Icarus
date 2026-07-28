# demo/test_library.py
"""The Library holds the active pipeline + status and switches repos: cache-hit
is instant, a miss ingests into a git-ignored cache, errors keep the old repo."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from evals.corpus_meta import write_meta
from evals.ingest import ICARUS_AST_CHUNKING_ENV
from .library import Library


def _seed_corpus(dir_, repo, commit="c0ffee", chunking="chunk_text"):
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "chunks.jsonl").write_text(json.dumps({"ref": "pr:1", "source": "pr", "text": "why"}) + "\n")
    write_meta(d / "meta.json", repo=repo, commit=commit, code_dir=".",
               counts={"pr": 1, "issue": 0, "code": 0}, chunking=chunking)


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

    def test_status_exposes_truncated_flag(self):
        # Brick 2a: /status carries whether the corpus was partially indexed.
        # A normal (untruncated) default corpus reports False, never omitted.
        self.assertFalse(self.lib.status_snapshot()["truncated"])

    def test_connect_uncached_ingests_then_switches(self):
        self.lib.connect_sync("octo/new")
        self.assertEqual(self.ingested, ["octo/new"])
        self.assertEqual(self.ingest_code_dirs, ["."])  # whole repo, not simonw/llm's `llm/`
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertEqual(s["repo"], "octo/new")

    def test_default_status_reports_no_phase(self):
        # Nothing in progress on the fully-ready default repo.
        self.assertIsNone(self.lib.status_snapshot()["phase"])

    def test_connect_reports_a_reading_phase_while_ingesting(self):
        # The app's progress line should say WHAT is happening, not spin silently.
        seen, holder = {}, {}

        def capturing_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            seen["phase"] = holder["lib"].status_snapshot()["phase"]
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                      build_pipeline=lambda d, fast=False: f"p::{d}", ingest_fn=capturing_ingest)
        holder["lib"] = lib
        lib.connect_sync("octo/x")
        self.assertEqual(seen["phase"], "Reading the repository…")

    def test_fully_ready_connect_clears_the_phase(self):
        # A sync connect blocks through the semantic upgrade, so by the time it
        # returns there is nothing pending -> phase is cleared.
        self.lib.connect_sync("octo/new")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "ready")
        self.assertIsNone(s["phase"])

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


class _AstChunkingEnvGuard(unittest.TestCase):
    """Always restores ICARUS_AST_CHUNKING -- a leak here would silently
    change every other test's staleness behavior in this process."""

    def setUp(self):
        self._prior = os.environ.get(ICARUS_AST_CHUNKING_ENV)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prior is None:
            os.environ.pop(ICARUS_AST_CHUNKING_ENV, None)
        else:
            os.environ[ICARUS_AST_CHUNKING_ENV] = self._prior

    def _set(self, value):
        if value is None:
            os.environ.pop(ICARUS_AST_CHUNKING_ENV, None)
        else:
            os.environ[ICARUS_AST_CHUNKING_ENV] = value


class ResolveStaysAvailabilityOnlyTests(_AstChunkingEnvGuard):
    """T6's central safety invariant: _resolve itself must NEVER report
    needs_ingest=True just because a corpus is stale -- only because it's
    genuinely missing. registry.py's eviction-replay path calls _resolve
    WITHOUT a token to decide whether an automatic resume is safe; if
    staleness leaked into _resolve, flipping ICARUS_AST_CHUNKING would make
    that path silently downgrade a resumed private-repo user to the public
    default the next time the flag changed -- exactly what its contract
    forbids. The staleness check belongs in connect_sync instead, the one
    caller with the authority (and, for a private repo, the token) to act on
    it."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.cache_root = root / "cache"
        self.private_root = root / "private"
        self.addCleanup(self.tmp.cleanup)
        self.lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                           build_pipeline=lambda d, fast=False: f"p::{d}",
                           ingest_fn=lambda *a, **k: {"pr": 0, "issue": 0, "code": 0},
                           private_root=self.private_root)

    def test_stale_public_corpus_still_reports_needs_ingest_false(self):
        _seed_corpus(self.cache_root / "octo__stale", "octo/stale", chunking="chunk_text")
        self._set("1")  # current scheme is now "ast" -- corpus is stale
        _, needs_ingest = self.lib._resolve("octo/stale")
        self.assertFalse(needs_ingest)

    def test_stale_private_corpus_still_reports_needs_ingest_false(self):
        _seed_corpus(self.private_root / "octo__stale", "octo/stale", chunking="chunk_text")
        self._set("1")
        _, needs_ingest = self.lib._resolve("octo/stale", private=True)
        self.assertFalse(needs_ingest)

    def test_genuinely_missing_corpus_still_reports_needs_ingest_true(self):
        # The one case _resolve DOES need to catch -- unaffected by any of this.
        _, needs_ingest = self.lib._resolve("never/connected")
        self.assertTrue(needs_ingest)


class CorpusIsStaleTests(_AstChunkingEnvGuard):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_matches_current_scheme_is_not_stale(self):
        _seed_corpus(self.dir, "o/r", chunking="chunk_text")
        self._set(None)  # off -> current scheme is chunk_text
        self.assertFalse(Library._corpus_is_stale(self.dir))

    def test_mismatches_current_scheme_is_stale(self):
        _seed_corpus(self.dir, "o/r", chunking="chunk_text")
        self._set("1")  # on -> current scheme is ast
        self.assertTrue(Library._corpus_is_stale(self.dir))

    def test_ast_corpus_stale_once_flag_turned_back_off(self):
        _seed_corpus(self.dir, "o/r", chunking="ast")
        self._set(None)
        self.assertTrue(Library._corpus_is_stale(self.dir))

    def test_pre_t6_corpus_with_no_chunking_field_treated_as_chunk_text(self):
        # A corpus ingested before this field existed at all.
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "meta.json").write_text(json.dumps({
            "repo": "o/r", "commit": "c0ffee", "code_dir": ".", "counts": {},
        }))
        self._set("1")  # current scheme is ast -- a pre-T6 corpus must count as stale
        self.assertTrue(Library._corpus_is_stale(self.dir))

    def test_missing_meta_json_is_not_treated_as_stale(self):
        # An unexpected, ambiguous state (chunks.jsonl with no meta.json) --
        # serve what's there rather than force a re-ingest on a hunch.
        self.dir.mkdir(parents=True, exist_ok=True)
        self._set("1")
        self.assertFalse(Library._corpus_is_stale(self.dir))

    def test_an_older_corpus_format_is_stale_even_on_the_matching_chunker(self):
        # THE deployment trap this guards. A repo connected before the
        # discussion landed (2026-07-28) has an identical `chunking` value, so
        # the chunker comparison alone says "fresh" and the corpus keeps
        # serving title-only PR chunks forever. The fix would be live on the
        # server and invisible to every user who already connected.
        self._set("1")
        _seed_corpus(self.dir, "o/r", chunking="ast")
        meta = json.loads((self.dir / "meta.json").read_text())
        meta["corpus_version"] = 1                      # pre-discussion corpus
        (self.dir / "meta.json").write_text(json.dumps(meta))
        self.assertEqual(meta["chunking"], "ast", "chunker must match, isolating the version")
        self.assertTrue(Library._corpus_is_stale(self.dir))

    def test_a_current_format_corpus_on_the_matching_chunker_is_not_stale(self):
        # The other direction: version checking must not force a permanent
        # re-ingest loop on a corpus that is already current.
        self._set("1")
        _seed_corpus(self.dir, "o/r", chunking="ast")
        self.assertFalse(Library._corpus_is_stale(self.dir))


class ConnectSyncStalenessTests(unittest.TestCase):
    """The actual T6 payoff: connect_sync refreshes a stale PUBLIC corpus
    automatically, refreshes a stale PRIVATE corpus when a token is
    available, and -- critically -- does NOT attempt a re-ingest for a
    stale private corpus with no token (the tokenless eviction-replay case),
    serving the existing corpus instead of failing."""

    def setUp(self):
        self._prior = os.environ.get(ICARUS_AST_CHUNKING_ENV)
        self.addCleanup(self._restore_env)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.cache_root = root / "cache"
        self.private_root = root / "private"
        self.ingested = []

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            self.ingested.append((repo, token))
            _seed_corpus(out_dir, repo, chunking="ast")  # simulates a fresh ingest under the new scheme
            return {"pr": 0, "issue": 0, "code": 0}

        self.lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                           build_pipeline=lambda d, fast=False: f"p::{d}",
                           ingest_fn=fake_ingest,
                           private_root=self.private_root,
                           private_ingest_fn=fake_ingest)

    def _restore_env(self):
        if self._prior is None:
            os.environ.pop(ICARUS_AST_CHUNKING_ENV, None)
        else:
            os.environ[ICARUS_AST_CHUNKING_ENV] = self._prior

    def test_stale_public_corpus_is_refreshed_on_connect(self):
        _seed_corpus(self.cache_root / "octo__stale", "octo/stale", chunking="chunk_text")
        os.environ[ICARUS_AST_CHUNKING_ENV] = "1"
        self.lib.connect_sync("octo/stale")
        self.assertEqual(self.ingested, [("octo/stale", None)])

    def test_fresh_public_corpus_is_not_reingested(self):
        _seed_corpus(self.cache_root / "octo__fresh", "octo/fresh", chunking="chunk_text")
        os.environ.pop(ICARUS_AST_CHUNKING_ENV, None)  # off -> chunk_text is current
        self.lib.connect_sync("octo/fresh")
        self.assertEqual(self.ingested, [])

    def test_stale_private_corpus_is_refreshed_when_token_present(self):
        _seed_corpus(self.private_root / "octo__stale", "octo/stale", chunking="chunk_text")
        os.environ[ICARUS_AST_CHUNKING_ENV] = "1"
        self.lib.connect_sync("octo/stale", private=True, token="ghp_real")
        self.assertEqual(self.ingested, [("octo/stale", "ghp_real")])

    def test_stale_private_corpus_without_token_is_served_not_reingested(self):
        # The tokenless eviction-replay case: must never attempt (and fail)
        # a re-ingest, and must never report an error -- just serve the
        # existing, if stale, corpus.
        _seed_corpus(self.private_root / "octo__stale", "octo/stale", chunking="chunk_text")
        os.environ[ICARUS_AST_CHUNKING_ENV] = "1"
        result = self.lib.connect_sync("octo/stale", private=True, token=None)
        self.assertEqual(self.ingested, [])
        self.assertEqual(result["state"], "ready")
        self.assertIsNone(result["error"])

    def test_default_repo_never_reingested_regardless_of_flag(self):
        os.environ[ICARUS_AST_CHUNKING_ENV] = "1"
        self.lib.connect_sync("simonw/llm")
        self.assertEqual(self.ingested, [])


class EmbedTimeoutScalingTests(unittest.TestCase):
    """The background semantic embed's wall-clock ceiling must SCALE with corpus
    size: a fixed 900s cap silently killed a big repo's embed (transformers, 50k
    chunks, ~an hour), leaving it stuck lexical-only. Small/medium repos keep the
    generous floor; large ones get proportional headroom."""

    def test_small_and_medium_repos_keep_the_floor(self):
        from demo.library import _embed_timeout, _EMBED_TIMEOUT_FLOOR_SECONDS
        self.assertEqual(_embed_timeout(0), _EMBED_TIMEOUT_FLOOR_SECONDS)
        self.assertEqual(_embed_timeout(470), _EMBED_TIMEOUT_FLOOR_SECONDS)   # default repo
        self.assertEqual(_embed_timeout(5000), _EMBED_TIMEOUT_FLOOR_SECONDS)  # still under floor

    def test_large_repo_gets_proportional_headroom(self):
        from demo.library import _embed_timeout, _EMBED_TIMEOUT_FLOOR_SECONDS, _EMBED_SECONDS_PER_CHUNK
        big = _embed_timeout(50000)
        self.assertGreater(big, _EMBED_TIMEOUT_FLOOR_SECONDS)          # not cut at the floor
        self.assertEqual(big, int(50000 * _EMBED_SECONDS_PER_CHUNK))   # ~0.1s/chunk


if __name__ == "__main__":
    unittest.main()
