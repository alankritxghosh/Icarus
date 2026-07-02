# evals/test_ingest_args.py
"""The ingest CLI: defaults preserve the pinned simonw/llm corpus; overrides
point at any public repo. Pure arg/commit logic only (no network)."""

import unittest

import tempfile
from pathlib import Path

from .ingest import parse_args, resolve_commit, _safe_code_dir, REPO, COMMIT


class ParseArgsTests(unittest.TestCase):
    def test_defaults_preserve_the_pin(self):
        a = parse_args([])
        self.assertEqual(a.repo, REPO)
        self.assertEqual(a.code_dir, "llm")
        self.assertIsNone(a.commit)

    def test_overrides(self):
        a = parse_args(["--repo", "octocat/hello", "--code-dir", "src", "--commit", "deadbeef"])
        self.assertEqual(a.repo, "octocat/hello")
        self.assertEqual(a.code_dir, "src")
        self.assertEqual(a.commit, "deadbeef")


class SafeCodeDirTests(unittest.TestCase):
    def test_rejects_escaping_paths(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                _safe_code_dir(d, "../../etc")
            with self.assertRaises(ValueError):
                _safe_code_dir(d, "/etc")

    def test_allows_subdirs_and_root(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_safe_code_dir(d, "llm"), Path(d).resolve() / "llm")
            self.assertEqual(_safe_code_dir(d, "."), Path(d).resolve())


class ResolveCommitTests(unittest.TestCase):
    def test_explicit_commit_wins(self):
        self.assertEqual(resolve_commit("octocat/hello", "feedface"), "feedface")

    def test_default_repo_without_commit_uses_pin(self):
        # default repo + no --commit must reproduce today's corpus (no network)
        self.assertEqual(resolve_commit(REPO, None), COMMIT)


if __name__ == "__main__":
    unittest.main()
