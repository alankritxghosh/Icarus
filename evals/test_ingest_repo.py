# evals/test_ingest_repo.py
"""ingest_repo writes chunks.jsonl + meta.json into any target dir and returns
counts. Offline: the network fetches are monkeypatched."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import ingest
from .corpus_meta import load_meta
from .ingest import (
    CHUNKING_SCHEME_AST,
    CHUNKING_SCHEME_LINE_WINDOW,
    ICARUS_AST_CHUNKING_ENV,
    _MAX_FILE_BYTES,
    _MAX_TOTAL_BYTES,
    REPO,
    _chunk_code,
    chunk_text,
)


class _EnvVarGuard(unittest.TestCase):
    """Base class: always restores ICARUS_AST_CHUNKING to its prior state,
    even on failure -- a leaked env var here would silently change every
    OTHER test's fetch_code behavior in the same process."""

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


class IngestRepoTests(_EnvVarGuard):
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

    def test_meta_stamps_chunk_text_scheme_when_flag_off(self):
        self._set(None)
        code = [{"ref": "code:a.py", "source": "code", "text": "x=1"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=([], set())), \
                mock.patch.object(ingest, "fetch_issues", return_value=[]), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".")
            m = load_meta(Path(d) / "meta.json")
            self.assertEqual(m["chunking"], CHUNKING_SCHEME_LINE_WINDOW)

    def test_meta_stamps_ast_scheme_when_flag_on(self):
        self._set("1")
        code = [{"ref": "code:a.py", "source": "code", "text": "x=1"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=([], set())), \
                mock.patch.object(ingest, "fetch_issues", return_value=[]), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".")
            m = load_meta(Path(d) / "meta.json")
            self.assertEqual(m["chunking"], CHUNKING_SCHEME_AST)


def _write(root, rel_path, content, binary=False):
    path = Path(root) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(content)
    return path


def _fake_run_cloning_fixture(fixture_root, calls=None):
    """Build a subprocess.run fake that, on `git fetch`, populates the working
    tree from `fixture_root` (copying real files) instead of touching the
    network -- so fetch_code walks a real fixture tree on disk without a live
    network fetch. `git init`/`remote add`/`checkout` and any `gh` calls are
    no-ops/empty. Every call is appended to `calls` if provided, so a test can
    assert on the git wire protocol itself (depth, target ref).
    """
    import shutil

    def fake_run(args, **kwargs):
        if calls is not None:
            calls.append(list(args))
        prog = args[0]
        if prog == "git" and args[1] == "init":
            return subprocess.CompletedProcess(args, 0, stdout="")
        if prog == "git" and args[1] == "-C" and "remote" in args:
            return subprocess.CompletedProcess(args, 0, stdout="")
        if prog == "git" and args[1] == "-C" and "fetch" in args:
            # The fetch is what materializes the tree, so this is where the
            # fixture lands (it was the `clone` before the shallow-fetch fix).
            dest = Path(args[2])
            shutil.copytree(fixture_root, dest, dirs_exist_ok=True)
            return subprocess.CompletedProcess(args, 0, stdout="")
        if prog == "git" and args[1] == "-C" and "checkout" in args:
            return subprocess.CompletedProcess(args, 0, stdout="")
        raise AssertionError(f"unexpected subprocess call in fetch_code test: {args}")

    return fake_run


class ShallowFetchTests(unittest.TestCase):
    """fetch_code must fetch ONLY the pinned commit, never full history.

    Found live 2026-07-17 while indexing real React Native repos: a
    full-history `git clone` of Expensify/App (2.7GB, the largest real public
    RN app) died with `fatal: early EOF` and blew the 120s subprocess timeout
    -- Icarus could not ingest it AT ALL, at any size cap. This was filed in
    docs/HANDOFF.md Part 3 as cosmetic "post-alpha hardening"; it is actually a
    hard blocker on exactly the customer-sized repos Icarus is sold into.

    The full clone was deliberate -- it kept an ARBITRARY pinned commit
    checkout-able, which `clone --depth 1` cannot do (that only gets a branch
    tip), and the eval board pins simonw/llm @ 94769b8. Fetching the SHA
    directly at depth 1 satisfies both: verified live at 27s on Expensify/App
    (vs. >120s hard failure) and 2s on the board's own pin, landing that exact
    SHA both times. These tests lock in the protocol so a future edit can't
    quietly reintroduce the full clone.
    """

    def _fetch_recording_calls(self, commit="deadbeef"):
        calls = []
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "pkg/ok.py", "x = 1\n")
            with mock.patch("evals.ingest.subprocess.run",
                            side_effect=_fake_run_cloning_fixture(fixture, calls)):
                ingest.fetch_code("octo/repo", commit, ".")
        return calls

    def test_never_performs_a_full_history_clone(self):
        # The actual defect: `git clone <url> <dir>` with no depth limit.
        for args in self._fetch_recording_calls():
            self.assertNotIn("clone", args,
                             f"full-history clone reintroduced: {args}")

    def test_fetches_the_pinned_commit_at_depth_one(self):
        calls = self._fetch_recording_calls(commit="94769b8b076cde9392059d76bd766453cf900180")
        fetches = [a for a in calls if "fetch" in a]
        self.assertEqual(len(fetches), 1, f"expected exactly one fetch, got {calls}")
        args = fetches[0]
        self.assertIn("--depth", args)
        self.assertEqual(args[args.index("--depth") + 1], "1")
        # The pinned SHA must be the fetch target -- that is what preserves the
        # board's byte-reproducible checkout without full history.
        self.assertIn("94769b8b076cde9392059d76bd766453cf900180", args)

    def test_checks_out_the_fetched_commit(self):
        calls = self._fetch_recording_calls()
        checkouts = [a for a in calls if "checkout" in a]
        self.assertEqual(len(checkouts), 1, f"expected exactly one checkout, got {calls}")
        self.assertIn("FETCH_HEAD", checkouts[0])


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

    def test_uppercase_extensions_classify_same_as_lowercase(self):
        """Regression test (found live 2026-07-13 against id-Software/wolf3d,
        the original Wolfenstein 3D source): classic DOS 8.3 uppercase
        filenames (ID_CA.C, ID_MM.C) made a whole real codebase silently
        invisible (code: 0, no error). Extension matching must be
        case-insensitive, but the citation ref must keep the file's real
        on-disk case -- never silently lowercase it."""
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "WOLFSRC/ID_CA.C", "void CA_Startup(void) {}\n")
            _write(fixture, "README.RST", "Original source release.\n")
            chunks = self._fetch(fixture)
            by_ref = {c["ref"]: c for c in chunks}
            self.assertEqual(by_ref["code:WOLFSRC/ID_CA.C"]["source"], "code")
            self.assertEqual(by_ref["doc:README.RST"]["source"], "doc")
            self.assertEqual(len(chunks), 2)

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

    def test_total_chunk_budget_stops_ingestion(self):
        # P1 fix (2026-07-13 review): a chunk-count cap bounds the lexical
        # stage-1 index even when a hostile repo stays under the BYTE cap (many
        # short lines). The walk stops at the next file boundary once the cap is
        # hit, so later files are skipped rather than exploding chunk count.
        with tempfile.TemporaryDirectory() as fixture, \
                mock.patch("evals.ingest._MAX_TOTAL_CHUNKS", 2):
            for name in ("a.py", "b.py", "c.py", "d.py"):
                _write(fixture, name, "x = 1\n")   # one chunk each, tiny
            chunks = self._fetch(fixture)
            refs = {c["ref"] for c in chunks}
            self.assertEqual(len(chunks), 2)       # stopped at the cap...
            self.assertNotIn("code:c.py", refs)    # ...later files were skipped
            self.assertNotIn("code:d.py", refs)

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

    def test_issue_list_call_requests_state_all_and_issue_limit(self):
        """Proves the literal `gh issue list --state all --limit ISSUE_LIMIT
        ...` args reach the subprocess call -- the exact test gap B1's own
        code-quality review flagged (every other test in this class mocks
        fetch_all_issue_ids out entirely, so none of them would catch a future
        edit that silently narrowed --state or dropped the limit). Mirrors
        FetchPRsAllStatesTests.test_pr_list_call_requests_state_all_not_merged's
        technique: patch subprocess.run directly and call the real function,
        not a mock of it, so the literal argv is captured."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[0] == "gh" and "list" in args:
                return subprocess.CompletedProcess(args, 0, stdout="[]")
            raise AssertionError(f"unexpected subprocess call: {args}")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            ingest.fetch_all_issue_ids("octo/repo")

        issue_list_calls = [c for c in calls if c[0] == "gh" and "list" in c]
        self.assertEqual(len(issue_list_calls), 1)
        call = issue_list_calls[0]
        self.assertIn("--state", call)
        self.assertEqual(call[call.index("--state") + 1], "all")
        self.assertIn("--limit", call)
        self.assertEqual(call[call.index("--limit") + 1], str(ingest.ISSUE_LIMIT))

    def test_issues_disabled_returns_empty_set_not_raise(self):
        """Regression test (found live 2026-07-13 against torvalds/linux and a
        small JS repo): `gh issue list` fails outright, not with an empty
        list, when a repo has Issues disabled -- a common, legitimate setting
        that previously made the ENTIRE ingest fail for an otherwise-ingestable
        repo. Must degrade to zero issues, not propagate."""
        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                1, args, output="", stderr="the 'octo/repo' repository has disabled issues\n")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            result = ingest.fetch_all_issue_ids("octo/repo")

        self.assertEqual(result, set())

    def test_other_called_process_error_still_raises(self):
        """The issues-disabled degrade must not become a blanket swallow of
        every gh failure -- an unrelated error (auth, network, rate limit)
        has to keep propagating so it isn't silently mistaken for zero
        issues."""
        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                1, args, output="", stderr="error connecting to api.github.com\n")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            with self.assertRaises(subprocess.CalledProcessError):
                ingest.fetch_all_issue_ids("octo/repo")

    def test_fetch_issues_uses_one_batched_call_not_one_per_issue(self):
        """Speedup (2026-07-15): fetch_issues makes ONE `gh issue list
        --json ...,body` call and filters to the wanted ids -- never a
        `gh issue view` per issue."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if "view" in args:
                raise AssertionError("fetch_issues must not call 'gh issue view' per issue")
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps([
                {"number": 10, "title": "ten", "body": "b10"},
                {"number": 20, "title": "twenty", "body": "b20"},
                {"number": 30, "title": "thirty", "body": "b30"},
            ]))

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            chunks = ingest.fetch_issues("octo/repo", {10, 30})

        self.assertEqual(len(calls), 1)  # ONE call for the whole set
        self.assertEqual({c["ref"] for c in chunks}, {"issue:10", "issue:30"})  # #20 filtered out

    def test_fetch_issues_empty_id_set_makes_no_call(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="[]")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            self.assertEqual(ingest.fetch_issues("octo/repo", set()), [])
        self.assertEqual(calls, [])  # nothing wanted -> no subprocess at all

    def test_issue_chunk_text_embeds_the_issue_number(self):
        """A question naming an issue by number (e.g. "issue #260") must have
        something to actually match against: the number itself, not just the
        title/body. Reproduces a live-found bug where an issue's own number
        was only ever in its `ref` ("issue:260"), never in its searchable
        `text` -- so a query for "#260" scored zero against its own chunk
        unless the title/body happened to mention the number by coincidence."""
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps([
                {"number": 10, "title": "ten", "body": "b10"},
            ]))

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            chunks = ingest.fetch_issues("octo/repo", {10})

        self.assertEqual(len(chunks), 1)
        self.assertIn("#10", chunks[0]["text"])

    def test_fetch_issues_degrades_on_disabled_issues_even_with_a_pr_mention(self):
        """A `#N` PR-body mention can leave issue_ids non-empty on a repo with
        Issues disabled; fetch_issues must degrade to [] like
        fetch_all_issue_ids, not fail the whole ingest."""
        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                1, args, output="", stderr="the 'x/y' repository has disabled issues\n")

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            self.assertEqual(ingest.fetch_issues("x/y", {5}), [])


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

    def test_fetch_prs_uses_one_batched_call_not_one_per_pr(self):
        """Speedup (2026-07-15): fetch_prs makes ONE `gh pr list --json ...,body`
        call for the whole repo, never a `gh pr view` per PR. Fixture returns 3
        PRs from the single list call and asserts no per-item view ever fires."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if "view" in args:
                raise AssertionError("fetch_prs must not call 'gh pr view' per PR anymore")
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps([
                {"number": 1, "title": "a", "body": "b1", "closingIssuesReferences": []},
                {"number": 2, "title": "b", "body": "b2", "closingIssuesReferences": []},
                {"number": 3, "title": "c", "body": "b3", "closingIssuesReferences": []},
            ]))

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            chunks, _ = ingest.fetch_prs("octo/repo")

        self.assertEqual(len(calls), 1)   # ONE call for THREE PRs (was 1 + 3)
        self.assertIn("--json", calls[0])
        self.assertIn("number,title,body,closingIssuesReferences", calls[0])
        self.assertEqual({c["ref"] for c in chunks}, {"pr:1", "pr:2", "pr:3"})

    def test_pr_chunk_text_embeds_the_pr_number(self):
        """Same reasoning as the issue-number embedding test above, for PRs:
        a query naming a PR by number must have the number itself to match
        against in the chunk's searchable text, not just its ref."""
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps([
                {"number": 42, "title": "a fix", "body": "b42", "closingIssuesReferences": []},
            ]))

        with mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            chunks, _ = ingest.fetch_prs("octo/repo")

        self.assertEqual(len(chunks), 1)
        self.assertIn("#42", chunks[0]["text"])

    def test_pr_chunks_produced_from_the_single_batched_list(self):
        """The batched `pr list --json` returns each PR's title/body/closing
        refs directly; fetch_prs turns every one into a chunk. (Fixture labels
        'open'/'merged' are narrative only -- the code never inspects state.)"""
        pr_list_result = [
            {"number": 1, "title": "Open PR title", "body": "closes #10",
             "closingIssuesReferences": []},
            {"number": 2, "title": "Merged PR title", "body": "fixes #20",
             "closingIssuesReferences": [{"number": 20}]},
        ]

        def fake_gh_json(args, token=None):
            if "list" in args:
                return pr_list_result
            raise AssertionError(f"unexpected _gh_json call (no per-PR view): {args}")

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
        pr_list_result = [{
            "number": 5,
            "title": "WIP: fix login",
            "body": "This will close #99 once reviewed. Also relates to #100.",
            "closingIssuesReferences": [{"number": 99}],
        }]

        def fake_gh_json(args, token=None):
            if "list" in args:
                return pr_list_result
            raise AssertionError(f"unexpected _gh_json call (no per-PR view): {args}")

        with mock.patch.object(ingest, "_gh_json", side_effect=fake_gh_json):
            chunks, issue_ids = ingest.fetch_prs("octo/repo")

        self.assertEqual(issue_ids, {99, 100})
        self.assertEqual(chunks[0]["ref"], "pr:5")


class FullCoverageEndToEndTests(unittest.TestCase):
    """Task B3: one combined, realistic fixture proving B1 (all issues) + B2
    (all PR states) both actually reach the FINAL counts dict and the written
    meta.json -- not just an intermediate call (that's what
    AllIssuesCoverageTests/FetchPRsAllStatesTests above already prove in
    isolation). Mixed PR states, a linked issue, and a standalone
    (benawad/vsinder#253-shaped) issue absent from any PR's references, all in
    one scenario, verified all the way through to disk."""

    def test_mixed_prs_and_issues_reach_final_counts_and_meta(self):
        # Two PRs: fixture labels "open"/"merged" are narrative color only --
        # fetch_prs' real pr-view call never inspects state (see
        # FetchPRsAllStatesTests above) -- both must count regardless.
        pr_list_result = [
            {"number": 1, "title": "Open PR: fix login", "body": "closes #10",
             "closingIssuesReferences": [{"number": 10}]},
            {"number": 2, "title": "Merged PR: add feature", "body": "no issue refs here",
             "closingIssuesReferences": []},
        ]
        # The full issue sweep now returns title+body in ONE list call (both
        # fetch_all_issue_ids and fetch_issues read it) -- includes #10 (linked
        # from PR 1) AND #253, a standalone issue never referenced by any PR
        # (the benawad/vsinder#253-shaped proof). No per-item view calls.
        issue_list_result = [
            {"number": 10, "title": "Linked issue: login broken", "body": "body for issue 10"},
            {"number": 253,
             "title": "Android app not displaying new matches and messages",
             "body": "body for issue 253"},
        ]

        def fake_gh_json(args, token=None):
            if "view" in args:
                raise AssertionError(f"no per-item view calls anymore: {args}")
            if "pr" in args and "list" in args:
                return pr_list_result
            if "issue" in args and "list" in args:
                # fetch_all_issue_ids asks for just 'number'; fetch_issues asks
                # for 'number,title,body'. The same fixture serves both.
                return issue_list_result
            raise AssertionError(f"unexpected _gh_json call: {args}")

        code = [{"ref": "code:main.py", "source": "code", "text": "x = 1\n"}]

        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(ingest, "_gh_json", side_effect=fake_gh_json), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            counts = ingest.ingest_repo("benawad/vsinder", out, commit="deadbeef", code_dir=".")

            # Both PRs counted regardless of state.
            self.assertEqual(counts["pr"], 2)
            # Both the linked issue (#10) AND the standalone issue (#253) counted.
            self.assertEqual(counts["issue"], 2)
            self.assertEqual(counts["code"], 1)

            chunks = [json.loads(l) for l in (Path(out) / "chunks.jsonl").read_text().splitlines() if l.strip()]
            refs = {c["ref"] for c in chunks}
            self.assertEqual(refs, {"pr:1", "pr:2", "issue:10", "issue:253", "code:main.py"})
            issue_253 = next(c for c in chunks if c["ref"] == "issue:253")
            self.assertIn("Android app not displaying new matches and messages", issue_253["text"])

            # meta.json (on disk, via load_meta) carries the SAME counts -- not
            # just the in-memory return value.
            meta = load_meta(Path(out) / "meta.json")
            self.assertEqual(meta["counts"]["pr"], 2)
            self.assertEqual(meta["counts"]["issue"], 2)
            self.assertEqual(meta["counts"]["code"], 1)
            self.assertEqual(meta["repo"], "benawad/vsinder")
            self.assertEqual(meta["commit"], "deadbeef")


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
        lowest level (git ls-remote / gh / git init / git remote add / git
        fetch / git checkout) and prove: the token string never appears in any
        `args` list, and the recorded `env` kwarg for git calls carries
        _git_env's header, for gh calls carries GH_TOKEN.

        The shallow-fetch fix (2026-07-17) widened this proof rather than
        narrowing it: the token must stay out of argv across FOUR git calls
        now, including the `remote add` that carries the clone URL -- the most
        tempting place for a credential to end up embedded."""
        token = "SECRET-TOKEN"
        calls = []

        def fake_run(args, **kwargs):
            calls.append({"args": list(args), "env": kwargs.get("env")})
            prog = args[0]
            if prog == "git" and args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout="deadbeef\tHEAD\n")
            if prog == "git" and args[1] == "init":
                Path(args[-1]).mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(args, 0, stdout="")
            if prog == "git" and args[1] == "-C":
                # covers `remote add`, `fetch --depth 1`, and `checkout`
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


class ChunkCodeDispatchTests(_EnvVarGuard):
    """_chunk_code (T4): dispatches a CODE file's text to the right chunker
    for its extension, behind ICARUS_AST_CHUNKING. Tests the DISPATCH
    decision in isolation (via mock.patch on ast_chunk/ts_chunk) -- whether
    those chunkers themselves produce good chunks is already proven by
    evals/test_ast_chunk.py, test_ast_chunking_eval.py, test_ts_chunk.py, and
    test_ts_chunking_eval.py (T1-T3); this file's job is only "does the right
    file extension reach the right function". Always runs -- ts_chunk.py
    imports cleanly without tree-sitter-language-pack installed (its own
    tree-sitter import is deferred inside _get_parser), so this needs no
    self-skip guard.
    """

    def test_default_off_never_calls_ast_chunk_or_ts_chunk(self):
        self._set(None)  # unset -- the real default, not just "0"
        with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
            result = _chunk_code("def f():\n    return 1\n", "code:a.py", ".py")
        m_ast.assert_not_called()
        m_ts.assert_not_called()
        self.assertEqual(result, chunk_text("def f():\n    return 1\n", "code:a.py"))

    def test_flag_off_explicitly_behaves_identically_to_unset(self):
        for off_value in ("0", "false", "no", "", "garbage"):
            with self.subTest(value=off_value):
                self._set(off_value)
                with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                        mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
                    _chunk_code("x = 1\n", "code:a.py", ".py")
                m_ast.assert_not_called()
                m_ts.assert_not_called()

    def test_flag_on_recognizes_common_truthy_spellings(self):
        for on_value in ("1", "true", "TRUE", "True", "yes", "YES"):
            with self.subTest(value=on_value):
                self._set(on_value)
                with mock.patch("evals.ast_chunk.ast_chunk") as m_ast:
                    _chunk_code("def f():\n    return 1\n", "code:a.py", ".py")
                m_ast.assert_called_once()

    def test_flag_on_routes_py_to_ast_chunk(self):
        self._set("1")
        with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
            _chunk_code("def f():\n    return 1\n", "code:a.py", ".py")
        m_ast.assert_called_once_with("def f():\n    return 1\n", "code:a.py")
        m_ts.assert_not_called()

    def test_flag_on_routes_react_native_languages_to_ts_chunk(self):
        self._set("1")
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mm", ".m", ".java", ".kt"):
            with self.subTest(ext=ext):
                with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                        mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
                    _chunk_code("irrelevant text", f"code:a{ext}", ext)
                m_ts.assert_called_once_with("irrelevant text", f"code:a{ext}", ext)
                m_ast.assert_not_called()

    def test_flag_on_still_leaves_h_on_chunk_text(self):
        # The deliberate exclusion (see ts_chunk.py's module docstring: both
        # the c and objc grammars produced too many ERROR nodes on real RN
        # headers) must survive the wiring, not just exist in ts_chunk.py's
        # own extension table.
        self._set("1")
        with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
            result = _chunk_code("void foo();\n", "code:a.h", ".h")
        m_ast.assert_not_called()
        m_ts.assert_not_called()
        self.assertEqual(result, chunk_text("void foo();\n", "code:a.h"))

    def test_flag_on_leaves_other_languages_on_chunk_text(self):
        # Go/Rust/Ruby/etc. have no ast_chunk/ts_chunk coverage at all --
        # confirm the flag doesn't accidentally route them somewhere broken.
        self._set("1")
        for ext in (".go", ".rs", ".rb", ".c", ".cpp", ".swift", ".php", ".cs", ".scala", ".sh"):
            with self.subTest(ext=ext):
                with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                        mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
                    result = _chunk_code("irrelevant", f"code:a{ext}", ext)
                m_ast.assert_not_called()
                m_ts.assert_not_called()
                self.assertEqual(result, chunk_text("irrelevant", f"code:a{ext}"))


class FetchCodeAstChunkingWiringTests(_EnvVarGuard):
    """The same dispatch, exercised through the real fetch_code walk (not
    just _chunk_code in isolation) -- proves doc/config sources never reach
    the dispatcher at all (only `source == "code"` should), and that the
    committed board's reproducibility is untouched when the flag is off
    (the real, load-bearing default)."""

    def _fetch(self, fixture_root, code_dir="."):
        with mock.patch("evals.ingest.subprocess.run",
                        side_effect=_fake_run_cloning_fixture(fixture_root)):
            return ingest.fetch_code("octo/repo", "deadbeef", code_dir)

    def test_default_off_matches_plain_chunk_text_byte_for_byte(self):
        self._set(None)
        src = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "pkg/mod.py", src)
            chunks = self._fetch(fixture)
        expected = chunk_text(src, "code:pkg/mod.py")
        self.assertEqual([{"ref": c["ref"], "text": c["text"]} for c in chunks],
                         [{"ref": e["ref"], "text": e["text"]} for e in expected])

    def test_flag_on_doc_and_config_files_never_reach_ast_ts_chunk(self):
        self._set("1")
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "README.md", "# Title\n\nSome docs about a function.\n")
            _write(fixture, "config/app.yaml", "name: icarus\nversion: 1\n")
            with mock.patch("evals.ast_chunk.ast_chunk") as m_ast, \
                    mock.patch("evals.ts_chunk.ts_chunk") as m_ts:
                self._fetch(fixture)
            m_ast.assert_not_called()
            m_ts.assert_not_called()

    def test_flag_on_python_code_file_is_chunked_differently_than_chunk_text(self):
        self._set("1")
        src = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
        with tempfile.TemporaryDirectory() as fixture:
            _write(fixture, "pkg/mod.py", src)
            chunks = self._fetch(fixture)
        # AST chunking splits this into two per-function chunks with #Lstart-Lend
        # refs; chunk_text's whole-file short-circuit would return ONE chunk
        # with no line-range suffix at all (well under the window/char caps).
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertIn("#L", c["ref"])


if __name__ == "__main__":
    unittest.main()
