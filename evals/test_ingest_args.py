# evals/test_ingest_args.py
"""The ingest CLI: defaults preserve the pinned simonw/llm corpus; overrides
point at any public repo. Pure arg/commit logic only (no network)."""

import unittest

from .ingest import parse_args, resolve_commit, REPO, COMMIT


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


class ResolveCommitTests(unittest.TestCase):
    def test_explicit_commit_wins(self):
        self.assertEqual(resolve_commit("octocat/hello", "feedface"), "feedface")

    def test_default_repo_without_commit_uses_pin(self):
        # default repo + no --commit must reproduce today's corpus (no network)
        self.assertEqual(resolve_commit(REPO, None), COMMIT)


if __name__ == "__main__":
    unittest.main()
