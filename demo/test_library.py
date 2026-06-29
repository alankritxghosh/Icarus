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

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm"):
            self.ingested.append(repo)
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
        def boom(repo, out_dir, commit=None, code_dir="llm"):
            raise RuntimeError("gh exploded")
        self.lib._ingest_fn = boom
        self.lib.connect_sync("bad/repo")
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertIn("gh exploded", s["error"])
        self.assertEqual(s["repo"], "simonw/llm")  # still on the old repo
        self.assertEqual(self.lib.current_pipeline(), f"pipeline::{self.default_dir}")


if __name__ == "__main__":
    unittest.main()
