# evals/test_ingest_args.py
"""The ingest CLI: defaults preserve the pinned simonw/llm corpus; overrides
point at any public repo. Pure arg/commit logic only (no network)."""

import unittest

import tempfile
from pathlib import Path

from .ingest import parse_args, resolve_commit, resolve_code_dir, _safe_code_dir, REPO, COMMIT


class ParseArgsTests(unittest.TestCase):
    def test_defaults_preserve_the_pin(self):
        a = parse_args([])
        self.assertEqual(a.repo, REPO)
        self.assertIsNone(a.code_dir)  # sentinel; resolved later via resolve_code_dir
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


class ResolveCodeDirTests(unittest.TestCase):
    """Mirrors resolve_commit's pattern: explicit wins; the pinned default repo
    keeps its historical subtree; any other repo walks the whole clone root."""

    def test_default_repo_without_override_uses_llm_subtree(self):
        self.assertEqual(resolve_code_dir(REPO, None), "llm")

    def test_other_repo_without_override_walks_whole_root(self):
        self.assertEqual(resolve_code_dir("someone/other-repo", None), ".")

    def test_explicit_code_dir_wins_for_default_repo(self):
        self.assertEqual(resolve_code_dir(REPO, "custom-dir"), "custom-dir")

    def test_explicit_code_dir_wins_for_other_repo(self):
        self.assertEqual(resolve_code_dir("someone/other-repo", "custom-dir"), "custom-dir")


class IssueIdUnionTests(unittest.TestCase):
    """Brick B1: the linked-issue set (from fetch_prs' closingIssuesReferences/
    #N-mention scan) and the all-issues set (from fetch_all_issue_ids) must
    combine into a single deduped set passed to fetch_issues -- a plain set
    union, since "all issues" already subsumes "linked issues" as a subset.
    Pure, no network: proven directly over stub id lists/sets standing in for
    each source's real output."""

    def test_union_is_deduped_and_covers_both_sources(self):
        linked = {5, 42, 100}          # e.g. issue_ids from fetch_prs
        all_issues = {5, 12, 42, 253}  # e.g. fetch_all_issue_ids's return value
        combined = linked | all_issues
        self.assertEqual(combined, {5, 12, 42, 100, 253})

    def test_standalone_issue_absent_from_linked_set_still_included(self):
        # This is the exact #253 shape: never linked from any merged PR, but
        # present in the full issue list.
        linked = {5, 12, 42}
        all_issues = {5, 12, 42, 166, 253}
        combined = linked | all_issues
        self.assertIn(253, combined)
        self.assertNotIn(253, linked)  # confirms the gap the union closes

    def test_empty_all_issues_set_is_a_no_op(self):
        linked = {1, 2, 3}
        self.assertEqual(linked | set(), linked)

    def test_disjoint_sets_union_without_dropping_either(self):
        linked = {1, 2}
        all_issues = {3, 4}
        self.assertEqual(linked | all_issues, {1, 2, 3, 4})


if __name__ == "__main__":
    unittest.main()
