# evals/test_ingest_commits.py
"""Commits are INDEXED, not merely resolvable by naming a SHA (2026-07-28).

They were deliberately excluded on the grounds that a real repo has too many --
which kept the densest "why" in any codebase out of search entirely. A commit
message is the one place a change explains itself at the moment it was made,
and until now you could only read one if you already knew its SHA.

Offline: `subprocess.run` is monkeypatched with git's real `--format` output
shape, verified against a live `git log` on psf/requests before these were
written (6,488 commits in 1.6s from a blobless fetch).
"""

import subprocess
import unittest
from unittest import mock

from . import ingest

_SHA = "c4367f231b5dc54f23f2983828562ce3a7555a8a"


def _record(sha, author, when, subject, body=""):
    """One `git log --format=%H%x00%an%x00%aI%x00%s%x00%b%x1e` record."""
    return f"{sha}\x00{author}\x00{when}\x00{subject}\x00{body}\x1e"


def _run_with(log_output, calls=None):
    def fake_run(args, **kwargs):
        if calls is not None:
            calls.append(list(args))
        if "log" in args:
            return subprocess.CompletedProcess(args, 0, stdout=log_output)
        return subprocess.CompletedProcess(args, 0, stdout="")
    return fake_run


def _fetch(log_output, stats=None, calls=None):
    with mock.patch("evals.ingest.subprocess.run", side_effect=_run_with(log_output, calls)):
        return ingest.fetch_commits("psf/requests", "deadbeef", stats=stats)


class CommitChunkTests(unittest.TestCase):
    def test_a_commit_becomes_a_chunk(self):
        out = _record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Add AI Policy")
        chunks = _fetch(out)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["source"], "commit")

    def test_the_ref_matches_the_live_lookup_format(self):
        # Load-bearing: fetch_commit_detail emits `commit:<full sha>` and
        # demo/links.ref_to_url parses that. An indexed commit that used a
        # different ref shape would produce citations that don't resolve.
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Add AI Policy"))
        self.assertEqual(chunks[0]["ref"], f"commit:{_SHA}")

    def test_the_subject_and_body_are_both_searchable(self):
        body = "The influx of low-quality pull requests is creating toil."
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Add AI Policy", body))
        self.assertIn("Add AI Policy", chunks[0]["text"])
        self.assertIn("low-quality pull requests", chunks[0]["text"])

    def test_the_author_and_date_are_recorded(self):
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Add AI Policy"))
        self.assertIn("Ian", chunks[0]["text"])
        self.assertIn("2026-05-31", chunks[0]["text"])

    def test_the_short_sha_leads_the_chunk(self):
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Add AI Policy"))
        self.assertTrue(chunks[0]["text"].startswith(f"COMMIT {_SHA[:7]}:"))


class ParsingTests(unittest.TestCase):
    """A commit message can contain newlines, tabs, and almost any printable
    byte, so the record/field delimiters have to be ones git itself forbids.
    These are the cases that would silently corrupt a whole corpus."""

    def test_a_multiline_body_survives_intact(self):
        body = "line one\nline two\n\nline four"
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "Subject", body))
        self.assertEqual(len(chunks), 1)
        for fragment in ("line one", "line two", "line four"):
            self.assertIn(fragment, chunks[0]["text"])

    def test_a_body_containing_delimiters_like_pipes_and_tabs_is_fine(self):
        body = "table | of | things\tand\ttabs"
        chunks = _fetch(_record(_SHA, "Ian", "2026-05-31T10:00:00Z", "S", body))
        self.assertEqual(len(chunks), 1)
        self.assertIn("table | of | things", chunks[0]["text"])

    def test_many_commits_parse_into_one_chunk_each(self):
        out = "".join(_record(f"{i:040x}", "a", "2026-01-01T00:00:00Z", f"s{i}")
                      for i in range(50))
        chunks = _fetch(out)
        self.assertEqual(len(chunks), 50)
        self.assertEqual(len({c["ref"] for c in chunks}), 50)

    def test_a_malformed_record_is_skipped_not_fatal(self):
        out = _record(_SHA, "a", "2026-01-01T00:00:00Z", "good") + "garbage-no-nulls\x1e"
        chunks = _fetch(out)
        self.assertEqual([c["ref"] for c in chunks], [f"commit:{_SHA}"])

    def test_empty_history_yields_nothing_and_does_not_raise(self):
        self.assertEqual(_fetch(""), [])

    def test_a_giant_message_is_truncated_and_marked(self):
        chunks = _fetch(_record(_SHA, "a", "2026-01-01T00:00:00Z", "s", "x" * 50000))
        text = chunks[0]["text"]
        self.assertLessEqual(len(text), ingest._REF_DETAIL_MAX_CHARS + 40)
        self.assertIn("truncated", text)


class FetchStrategyTests(unittest.TestCase):
    """The fetch has to be blobless and bounded, or indexing history costs more
    than indexing the code. Measured on psf/requests: 6,488 commits in 1.6s
    into a 3.6 MB .git, because file contents are never transferred."""

    def _calls(self):
        calls = []
        _fetch(_record(_SHA, "a", "2026-01-01T00:00:00Z", "s"), calls=calls)
        return calls

    def test_the_fetch_skips_blobs(self):
        fetches = [c for c in self._calls() if "fetch" in c]
        self.assertTrue(fetches)
        self.assertIn("--filter=blob:none", fetches[0])

    def test_the_fetch_depth_is_bounded_by_the_cap(self):
        fetches = [c for c in self._calls() if "fetch" in c]
        self.assertIn("--depth", fetches[0])
        self.assertEqual(fetches[0][fetches[0].index("--depth") + 1], str(ingest.COMMIT_LIMIT))

    def test_the_log_is_bounded_by_the_cap(self):
        logs = [c for c in self._calls() if "log" in c]
        self.assertTrue(logs)
        self.assertIn(f"--max-count={ingest.COMMIT_LIMIT}", logs[0])

    def test_no_per_commit_diff_is_computed(self):
        # --name-only costs a tree diff per commit: measured 27s against 2s on
        # psf/requests, for information the PR-level file list already carries.
        for call in self._calls():
            self.assertNotIn("--name-only", call)
            self.assertNotIn("--numstat", call)


class DisclosureTests(unittest.TestCase):
    def test_hitting_the_commit_cap_is_disclosed(self):
        stats = {}
        out = "".join(_record(f"{i:040x}", "a", "2026-01-01T00:00:00Z", "s")
                      for i in range(ingest.COMMIT_LIMIT))
        _fetch(out, stats=stats)
        self.assertTrue(stats.get("truncated"),
                        "a partial commit history must never read as complete")

    def test_a_repo_under_the_cap_is_not_flagged(self):
        stats = {}
        _fetch(_record(_SHA, "a", "2026-01-01T00:00:00Z", "s"), stats=stats)
        self.assertFalse(stats.get("truncated"))


class WiringTests(unittest.TestCase):
    def test_ingest_repo_includes_commits_in_the_corpus_and_counts(self):
        import json
        import tempfile
        from pathlib import Path
        commits = [{"ref": f"commit:{_SHA}", "source": "commit", "text": "COMMIT c4367f2: s"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=([], set())), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch.object(ingest, "fetch_issues", return_value=[]), \
                mock.patch.object(ingest, "fetch_commits", return_value=commits), \
                mock.patch.object(ingest, "fetch_code", return_value=[]):
            counts = ingest.ingest_repo("o/r", d, commit="abc", code_dir=".")
            written = [json.loads(l) for l in
                       (Path(d) / "chunks.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(counts["commit"], 1)
        self.assertEqual([c["ref"] for c in written], [f"commit:{_SHA}"])


if __name__ == "__main__":
    unittest.main()
