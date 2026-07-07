# evals/test_ingest_repo.py
"""ingest_repo writes chunks.jsonl + meta.json into any target dir and returns
counts. Offline: the network fetches are monkeypatched."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import ingest
from .corpus_meta import load_meta
from .ingest import _MAX_FILE_BYTES, _MAX_TOTAL_BYTES, REPO


class IngestRepoTests(unittest.TestCase):
    def test_writes_corpus_and_meta_to_target_dir(self):
        prs = ([{"ref": "pr:1", "source": "pr", "text": "why X"}], {7})
        issues = [{"ref": "issue:7", "source": "issue", "text": "ctx"}]
        code = [{"ref": "code:a.py", "source": "code", "text": "x=1"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=issues), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            counts = ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".")
            chunks = [json.loads(l) for l in (Path(d) / "chunks.jsonl").read_text().splitlines() if l.strip()]
            self.assertEqual([c["ref"] for c in chunks], ["pr:1", "issue:7", "code:a.py"])
            self.assertEqual(counts, {"pr": 1, "issue": 1, "code": 1})
            m = load_meta(Path(d) / "meta.json")
            self.assertEqual(m["repo"], "octo/repo")
            self.assertEqual(m["commit"], "abc123")


def _write(root, rel_path, content, binary=False):
    path = Path(root) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(content)
    return path


def _fake_run_cloning_fixture(fixture_root):
    """Build a subprocess.run fake that, on `git clone`, populates the clone
    destination from `fixture_root` (copying real files) instead of touching
    the network -- so fetch_code walks a real fixture tree on disk without a
    live clone. `git checkout` and any `gh` calls are no-ops/empty."""
    import shutil

    def fake_run(args, **kwargs):
        prog = args[0]
        if prog == "git" and args[1] == "clone":
            dest = Path(args[-1])
            shutil.copytree(fixture_root, dest, dirs_exist_ok=True)
            return subprocess.CompletedProcess(args, 0, stdout="")
        if prog == "git" and args[1] == "-C" and "checkout" in args:
            return subprocess.CompletedProcess(args, 0, stdout="")
        raise AssertionError(f"unexpected subprocess call in fetch_code test: {args}")

    return fake_run


class FetchCodeWholeRepoWalkTests(unittest.TestCase):
    """fetch_code (Task A3): walks every file under code_dir (not just *.py),
    classifies each via classify_file, chunks via chunk_text, and re-adds the
    "source" key chunk_text deliberately omits. All offline: `git clone` is
    monkeypatched to copy a fixture tree instead of hitting the network."""

    def _fetch(self, fixture_root, code_dir="."):
        with mock.patch("evals.ingest.subprocess.run",
                         side_effect=_fake_run_cloning_fixture(fixture_root)):
            return ingest.fetch_code("octo/repo", "deadbeef", code_dir)

    def test_walks_mixed_file_types_with_correct_source_tags(self):
        with tempfile.TemporaryDirectory() as fixture, tempfile.TemporaryDirectory():
            _write(fixture, "pkg/main.go", "package main\n\nfunc main() {}\n")
            _write(fixture, "README.md", "# Title\n\nSome docs.\n")
            _write(fixture, "config/app.yaml", "name: icarus\n")
            chunks = self._fetch(fixture)
            by_ref = {c["ref"]: c for c in chunks}
            self.assertEqual(by_ref["code:pkg/main.go"]["source"], "code")
            self.assertEqual(by_ref["doc:README.md"]["source"], "doc")
            self.assertEqual(by_ref["config:config/app.yaml"]["source"], "config")
            self.assertEqual(len(chunks), 3)

    def test_deny_listed_binary_and_oversized_files_excluded(self):
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "node_modules/left-pad/index.js", "module.exports = 1;\n")
            _write(fixture, "pkg/blob.py", b"\x00\x01binary junk", binary=True)
            _write(fixture, "pkg/huge.py", "x = 1\n" * (_MAX_FILE_BYTES // 6 + 1000))
            _write(fixture, "pkg/ok.py", "x = 1\n")
            chunks = self._fetch(fixture)
            refs = {c["ref"] for c in chunks}
            self.assertEqual(refs, {"code:pkg/ok.py"})

    def test_large_file_produces_multiple_windowed_chunks_with_source(self):
        with tempfile.TemporaryDirectory() as fixture:
            big_text = "\n".join(f"line {i}" for i in range(1, 501)) + "\n"  # > 300 lines
            _write(fixture, "pkg/big.py", big_text)
            chunks = self._fetch(fixture)
            self.assertGreater(len(chunks), 1)
            for c in chunks:
                self.assertEqual(c["source"], "code")
                self.assertTrue(c["ref"].startswith("code:pkg/big.py#L"))
            # first window starts at line 1, last window ends at line 500
            self.assertTrue(chunks[0]["ref"].endswith("#L1-L300"))
            self.assertTrue(chunks[-1]["ref"].endswith("-L500"))

    def test_total_byte_budget_stops_ingestion_across_mixed_sources(self):
        with tempfile.TemporaryDirectory() as fixture, \
                mock.patch("evals.ingest._MAX_TOTAL_BYTES", 100):
            # Each file is well under _MAX_FILE_BYTES but together exceed the
            # patched small total budget -- some files must be skipped.
            _write(fixture, "a.py", "x = 1\n" * 20)     # ~120 bytes
            _write(fixture, "b.md", "# doc\n" * 20)      # ~120 bytes
            _write(fixture, "c.yaml", "k: v\n" * 20)      # ~100 bytes
            chunks = self._fetch(fixture)
            total = sum(len(c["text"].encode("utf-8")) for c in chunks)
            # Budget enforced: not all three files' bytes made it in.
            self.assertLessEqual(len(chunks), 2)
            self.assertLess(total, 400)  # far less than all three files combined

    def test_counts_reflect_mixed_sources_via_ingest_repo(self):
        prs = ([], set())
        issues = []
        with tempfile.TemporaryDirectory() as fixture, tempfile.TemporaryDirectory() as out, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=issues), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch("evals.ingest.subprocess.run",
                           side_effect=_fake_run_cloning_fixture(fixture)):
            _write(fixture, "pkg/main.go", "package main\n\nfunc main() {}\n")
            _write(fixture, "README.md", "# Title\n\nSome docs.\n")
            _write(fixture, "config/app.yaml", "name: icarus\n")
            counts = ingest.ingest_repo("octo/repo", out, commit="deadbeef", code_dir=".")
            self.assertEqual(counts.get("code"), 1)
            self.assertEqual(counts.get("doc"), 1)
            self.assertEqual(counts.get("config"), 1)
            self.assertEqual(counts.get("pr"), 0)
            self.assertEqual(counts.get("issue"), 0)

    def test_empty_repo_yields_no_chunks(self):
        # A tree containing only deny-listed paths (no ingestable file at all)
        # must not crash -- the walk just yields nothing.
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "node_modules/left-pad/index.js", "module.exports = 1;\n")
            _write(fixture, ".git/HEAD", "ref: refs/heads/main\n")
            chunks = self._fetch(fixture)
            self.assertEqual(chunks, [])

    def test_genuinely_empty_directory_yields_no_chunks(self):
        with tempfile.TemporaryDirectory() as fixture:
            chunks = self._fetch(fixture)
            self.assertEqual(chunks, [])

    def test_nonzero_pr_and_issue_counts_pass_through_unchanged(self):
        """The counts-building rewrite buckets code by source dynamically --
        prove it left PR/issue accounting alone by feeding non-trivial mocked
        counts (2 PRs, 3 issues) alongside a real mixed-source code walk, and
        asserting the exact numbers flow through into the final counts dict."""
        prs = (
            [{"ref": "pr:1", "source": "pr", "text": "why X"},
             {"ref": "pr:2", "source": "pr", "text": "why Y"}],
            {10, 11, 12},
        )
        issues = [
            {"ref": "issue:10", "source": "issue", "text": "ctx A"},
            {"ref": "issue:11", "source": "issue", "text": "ctx B"},
            {"ref": "issue:12", "source": "issue", "text": "ctx C"},
        ]
        with tempfile.TemporaryDirectory() as fixture, tempfile.TemporaryDirectory() as out, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=issues), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch("evals.ingest.subprocess.run",
                           side_effect=_fake_run_cloning_fixture(fixture)):
            _write(fixture, "pkg/main.go", "package main\n\nfunc main() {}\n")
            _write(fixture, "README.md", "# Title\n\nSome docs.\n")
            counts = ingest.ingest_repo("octo/repo", out, commit="deadbeef", code_dir=".")
            self.assertEqual(counts.get("pr"), 2)
            self.assertEqual(counts.get("issue"), 3)
            self.assertEqual(counts.get("code"), 1)
            self.assertEqual(counts.get("doc"), 1)


class AllIssuesCoverageTests(unittest.TestCase):
    """Brick B1 regression test for the benawad/vsinder #253 coverage gap: a
    standalone issue, never linked from any merged PR (so absent from
    fetch_prs' issue_ids), must still reach fetch_issues via
    fetch_all_issue_ids's full open+closed issue-number sweep."""

    def test_standalone_unlinked_issue_reaches_fetch_issues(self):
        # fetch_prs returns only issue #42, linked from a merged PR's
        # closingIssuesReferences/#N mention -- #253 is never mentioned here,
        # mirroring the real vsinder repro (a standalone OPEN issue).
        prs = ([{"ref": "pr:1", "source": "pr", "text": "why X"}], {42})
        code = []

        captured_issue_ids = {}

        def fake_fetch_issues(repo, issue_ids, token=None):
            captured_issue_ids["value"] = set(issue_ids)
            return [{"ref": f"issue:{n}", "source": "issue", "text": "x"} for n in issue_ids]

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", side_effect=fake_fetch_issues), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value={42, 253}), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            ingest.ingest_repo("benawad/vsinder", d, commit="abc123", code_dir=".")

        self.assertIn(42, captured_issue_ids["value"])   # linked issue kept
        self.assertIn(253, captured_issue_ids["value"])  # standalone issue now included

    def test_fetch_all_issue_ids_called_with_repo_and_token(self):
        prs = ([], set())
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=[]) as mock_fetch_issues, \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()) as mock_all_ids, \
                mock.patch.object(ingest, "fetch_code", return_value=[]):
            ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".", token="tok")

        mock_all_ids.assert_called_once_with("octo/repo", token="tok")
        mock_fetch_issues.assert_called_once()


class FetchPRsAllStatesTests(unittest.TestCase):
    """Brick B2: fetch_prs must fetch PRs of ALL states (open+closed+merged),
    not just merged -- closes the coverage gap where an open PR (and any issue
    it alone references) was invisible. Guarded by the same PR_LIMIT, no new
    limit constant."""

    def test_pr_list_call_requests_state_all_not_merged(self):
        """Proves the literal `gh pr list --state all ...` args reach the
        subprocess call -- the exact test gap B1's review flagged for the
        analogous `gh issue list` change, closed here from day one."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[0] == "gh" and "list" in args:
                return subprocess.CompletedProcess(args, 0, stdout="[]")
            raise AssertionError(f"unexpected subprocess call: {args}")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            ingest.fetch_prs("octo/repo")

        pr_list_calls = [c for c in calls if c[0] == "gh" and "list" in c]
        self.assertEqual(len(pr_list_calls), 1)
        call = pr_list_calls[0]
        self.assertIn("--state", call)
        self.assertEqual(call[call.index("--state") + 1], "all")
        self.assertNotIn("merged", call)
        # PR_LIMIT is still the only cap on this call.
        self.assertIn("--limit", call)
        self.assertEqual(call[call.index("--limit") + 1], str(ingest.PR_LIMIT))

    def test_pr_chunks_produced_regardless_of_which_pr_numbers_are_returned(self):
        """Integration-style: fetch_prs' pr view call only ever requests
        title/body/closingIssuesReferences -- it never fetches or branches on
        a PR's actual state. So this proves the loop is uniform across two
        different PR numbers from `pr list --state all`, not literally "open
        vs. merged behave differently" (they never can, by design). The
        "open"/"merged" labels below are narrative color for the fixture data
        only, not something the code inspects."""
        pr_list_result = [{"number": 1}, {"number": 2}]
        pr_views = {
            1: {"title": "Open PR title", "body": "closes #10", "closingIssuesReferences": []},
            2: {"title": "Merged PR title", "body": "fixes #20",
                "closingIssuesReferences": [{"number": 20}]},
        }

        def fake_gh_json(args, token=None):
            if "list" in args:
                return pr_list_result
            if "view" in args:
                n = int(args[args.index("view") + 1])
                return pr_views[n]
            raise AssertionError(f"unexpected _gh_json call: {args}")

        with mock.patch.object(ingest, "_gh_json", side_effect=fake_gh_json):
            chunks, issue_ids = ingest.fetch_prs("octo/repo")

        by_ref = {c["ref"]: c for c in chunks}
        self.assertIn("pr:1", by_ref)
        self.assertIn("pr:2", by_ref)
        self.assertEqual(by_ref["pr:1"]["source"], "pr")
        self.assertEqual(by_ref["pr:2"]["source"], "pr")
        self.assertIn("Open PR title", by_ref["pr:1"]["text"])
        self.assertIn("Merged PR title", by_ref["pr:2"]["text"])

    def test_issue_reference_scanning_still_works_on_a_pr_returned_by_state_all(self):
        """The closingIssuesReferences + #N regex scan must not have any
        hidden assumption baked in from the old merged-only fetch. Note:
        fetch_prs' pr view call never requests or inspects a PR's state, so
        this doesn't (and can't) prove open-vs-merged branching -- it proves
        the scan still fires correctly for a PR number reached via the new
        `--state all` list call."""
        pr_list_result = [{"number": 5}]
        pr_view = {
            "title": "WIP: fix login",
            "body": "This will close #99 once reviewed. Also relates to #100.",
            "closingIssuesReferences": [{"number": 99}],
        }

        def fake_gh_json(args, token=None):
            if "list" in args:
                return pr_list_result
            if "view" in args:
                return pr_view
            raise AssertionError(f"unexpected _gh_json call: {args}")

        with mock.patch.object(ingest, "_gh_json", side_effect=fake_gh_json):
            chunks, issue_ids = ingest.fetch_prs("octo/repo")

        self.assertEqual(issue_ids, {99, 100})
        self.assertEqual(chunks[0]["ref"], "pr:5")


class ResolveCodeDirIntegrationTests(unittest.TestCase):
    """The no-arg / default-repo path resolves code_dir to "llm"; any other
    repo resolves to "." -- verified via the resolve_code_dir helper itself
    (the pure logic ingest_repo's caller, main(), relies on)."""

    def test_default_repo_resolves_to_llm_subtree(self):
        self.assertEqual(ingest.resolve_code_dir(REPO, None), "llm")

    def test_other_repo_resolves_to_whole_root(self):
        self.assertEqual(ingest.resolve_code_dir("someone/other-repo", None), ".")


class AuthenticatedIngestTests(unittest.TestCase):
    """The caller's token authenticates git+gh — via ENV ONLY. argv shows in
    `ps`, URLs land in git config: both are leaks."""

    def test_git_env_carries_basic_auth_never_argv(self):
        from evals.ingest import _git_env
        env = _git_env("SECRET-TOKEN")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.extraHeader")
        self.assertTrue(env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic "))
        self.assertNotIn("SECRET-TOKEN", env["GIT_CONFIG_VALUE_0"])  # b64, not raw
        import base64
        b64 = env["GIT_CONFIG_VALUE_0"].split()[-1]
        self.assertEqual(base64.b64decode(b64).decode(), "x-access-token:SECRET-TOKEN")

    def test_git_env_without_token_is_plain(self):
        import os
        from evals.ingest import _git_env
        self.assertNotIn("GIT_CONFIG_COUNT", set(_git_env(None)) - set(os.environ))

    def test_gh_env_sets_gh_token(self):
        from evals.ingest import _gh_env
        self.assertEqual(_gh_env("SECRET")["GH_TOKEN"], "SECRET")

    def test_token_reaches_subprocess_env_never_args(self):
        """Drive a real ingest_repo(...) call with subprocess.run faked at the
        lowest level (git ls-remote / gh / git clone / git checkout) and prove:
        the token string never appears in any `args` list, and the recorded
        `env` kwarg for git calls carries _git_env's header, for gh calls
        carries GH_TOKEN."""
        token = "SECRET-TOKEN"
        calls = []

        def fake_run(args, **kwargs):
            calls.append({"args": list(args), "env": kwargs.get("env")})
            prog = args[0]
            if prog == "git" and args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout="deadbeef\tHEAD\n")
            if prog == "git" and args[1] == "clone":
                dest = Path(args[-1])
                dest.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(args, 0, stdout="")
            if prog == "git" and args[1] == "-C":
                return subprocess.CompletedProcess(args, 0, stdout="")
            if prog == "gh":
                if "pr" in args and "list" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="[]")
                if "issue" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="{}")
                return subprocess.CompletedProcess(args, 0, stdout="[]")
            raise AssertionError(f"unexpected subprocess call: {args}")

        with tempfile.TemporaryDirectory() as d, \
                mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            ingest.ingest_repo("octo/private-repo", d, code_dir=".", token=token)

        self.assertTrue(calls, "expected at least one subprocess.run call")
        for call in calls:
            for arg in call["args"]:
                self.assertNotIn(token, str(arg))

        git_calls = [c for c in calls if c["args"][0] == "git"]
        gh_calls = [c for c in calls if c["args"][0] == "gh"]
        self.assertTrue(git_calls)
        self.assertTrue(gh_calls)
        for c in git_calls:
            self.assertEqual(c["env"]["GIT_CONFIG_VALUE_0"],
                              ingest._git_env(token)["GIT_CONFIG_VALUE_0"])
        for c in gh_calls:
            self.assertEqual(c["env"]["GH_TOKEN"], token)


if __name__ == "__main__":
    unittest.main()
