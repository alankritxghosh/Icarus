# evals/test_ingest_discussion.py
"""RED failing eval for a live-found gap (2026-07-28, raised by Alankrit): the
reason a change was made is usually recorded in the PR's DISCUSSION, not its
description -- and the indexed path stored only `title` + `body`.

That produced the worst possible failure for this product: an honest "no one
wrote this down" about something the team HAD written down, three comments
further in. Not a bluff -- Icarus never fabricated anything -- but a customer
cannot distinguish "nobody recorded this" from "you didn't read it", and the
whole promise rests on that distinction being trustworthy.

The asymmetry that hid it: `fetch_ref_detail` (the LIVE path, used only for a
`#N` OUTSIDE the indexed slice) already fetched comments. So old, unindexed PRs
answered richly while the most recent ones -- the ones anyone actually asks
about -- answered from the description alone.

These tests are offline: `_gh_json` is monkeypatched with the real field shapes,
verified against `gh pr list -R psf/requests --json …` before they were written.
"""

import subprocess
import unittest
from unittest import mock

from . import ingest


def _pr(number, title, body, *, comments=(), reviews=(), files=(),
        state="MERGED", author="octocat", merged_at="2026-01-01T00:00:00Z",
        labels=()):
    """One `gh pr list --json …` item, in gh's real shape."""
    return {
        "number": number,
        "title": title,
        "body": body,
        "closingIssuesReferences": [],
        "state": state,
        "author": {"login": author, "is_bot": False},
        "mergedAt": merged_at,
        "labels": [{"name": n} for n in labels],
        "files": [{"path": p, "additions": a, "deletions": d} for p, a, d in files],
        "comments": [{"body": b, "author": {"login": who}} for who, b in comments],
        "reviews": [{"body": b, "author": {"login": who}, "state": st}
                    for who, b, st in reviews],
    }


def _issue(number, title, body, *, comments=()):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": "CLOSED",
        "author": {"login": "octocat", "is_bot": False},
        "labels": [],
        "comments": [{"body": b, "author": {"login": who}} for who, b in comments],
    }


def _text_for(chunks, ref):
    return next(c["text"] for c in chunks if c["ref"] == ref)


class ReasonLivesInTheDiscussionTests(unittest.TestCase):
    """The headline gap: the WHY is in a comment, and the description doesn't
    say it. This is the exact shape of a real PR review thread."""

    REASON = "we cap it at 30 because Firefox used 20 and we wanted headroom"

    def _prs(self):
        return [_pr(6952, "Add redirect limit", "Adds a constant for the redirect limit.",
                    comments=[("kennethreitz", self.REASON)])]

    def test_a_comment_only_reason_is_ingested(self):
        with mock.patch.object(ingest, "_gh_json", return_value=self._prs()):
            chunks, _ = ingest.fetch_prs("psf/requests")
        self.assertIn(self.REASON, _text_for(chunks, "pr:6952"))

    def test_the_commenter_is_attributed(self):
        # Who said it is part of the evidence -- "a maintainer said X" and
        # "a drive-by commenter said X" are not the same claim.
        with mock.patch.object(ingest, "_gh_json", return_value=self._prs()):
            chunks, _ = ingest.fetch_prs("psf/requests")
        self.assertIn("kennethreitz", _text_for(chunks, "pr:6952"))

    def test_the_ref_is_still_one_chunk_per_pr(self):
        # Load-bearing: GatedPipeline.answer()'s anchor looks up `pr:6952` in
        # _by_ref by exact key. Windowing this into `pr:6952#L1-L300` would
        # silently break the named-ref anchor fixed in a98df76.
        with mock.patch.object(ingest, "_gh_json", return_value=self._prs()):
            chunks, _ = ingest.fetch_prs("psf/requests")
        self.assertEqual([c["ref"] for c in chunks], ["pr:6952"])
        self.assertEqual(chunks[0]["source"], "pr")


class ReviewThreadsTests(unittest.TestCase):
    def test_a_review_body_is_ingested(self):
        objection = "this will break streaming responses"
        prs = [_pr(10, "Refactor", "body",
                   reviews=[("dev", objection, "CHANGES_REQUESTED")])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertIn(objection, _text_for(chunks, "pr:10"))

    def test_the_review_verdict_is_ingested(self):
        prs = [_pr(10, "Refactor", "body", reviews=[("dev", "no", "CHANGES_REQUESTED")])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertIn("CHANGES_REQUESTED", _text_for(chunks, "pr:10"))

    def test_an_empty_review_body_is_dropped_not_rendered_blank(self):
        # An APPROVED review with no body is the commonest review of all;
        # emitting "Review by x (APPROVED):" with nothing after it is noise
        # that dilutes BM25 across every PR in the corpus.
        prs = [_pr(10, "Refactor", "body", reviews=[("dev", "", "APPROVED")])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertNotIn("Review by dev", _text_for(chunks, "pr:10"))


class WhatChangedTests(unittest.TestCase):
    """"What did PR N change?" was answerable only from the description. The
    changed-file list makes it answerable from the change itself. Hunks are NOT
    fetched -- that needs a per-PR `gh pr diff` (N+1) -- so this is file-level
    truth, and the honest ceiling is stated in the module docstring."""

    def test_changed_files_are_ingested(self):
        prs = [_pr(11, "Fix", "body", files=[("requests/models.py", 12, 3)])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertIn("requests/models.py", _text_for(chunks, "pr:11"))

    def test_line_counts_are_ingested(self):
        prs = [_pr(11, "Fix", "body", files=[("requests/models.py", 12, 3)])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertIn("+12", _text_for(chunks, "pr:11"))

    def test_the_file_list_is_bounded(self):
        # A sweeping refactor can touch thousands of files; the list must not
        # crowd the discussion out of the writer's 10k-char view of this chunk.
        prs = [_pr(12, "Big", "body",
                   files=[(f"src/f{i}.py", 1, 1) for i in range(500)])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:12")
        self.assertIn("more file", text, "a truncated file list must say so")
        self.assertLess(text.count("src/f"), 100)


class MetadataTests(unittest.TestCase):
    def test_merge_state_and_author_are_ingested(self):
        prs = [_pr(13, "T", "b", state="MERGED", author="alice")]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:13")
        self.assertIn("MERGED", text)
        self.assertIn("alice", text)

    def test_an_open_pr_is_not_described_as_merged(self):
        prs = [_pr(14, "T", "b", state="OPEN", merged_at=None)]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:14")
        self.assertIn("OPEN", text)
        self.assertNotIn("MERGED", text)


class IssueDiscussionTests(unittest.TestCase):
    def test_an_issue_comment_is_ingested(self):
        reason = "closing: superseded by the new adapter API"
        with mock.patch.object(ingest, "_gh_json",
                               return_value=[_issue(42, "Bug", "steps to reproduce",
                                                    comments=[("maintainer", reason)])]):
            chunks = ingest.fetch_issues("r/r", {42})
        self.assertIn(reason, _text_for(chunks, "issue:42"))

    def test_the_issue_ref_is_still_one_chunk(self):
        with mock.patch.object(ingest, "_gh_json",
                               return_value=[_issue(42, "Bug", "body")]):
            chunks = ingest.fetch_issues("r/r", {42})
        self.assertEqual([c["ref"] for c in chunks], ["issue:42"])


class BoundsAndBackCompatTests(unittest.TestCase):
    def test_a_huge_thread_is_truncated_and_marked(self):
        # Same bound the LIVE path has always used, so both paths behave
        # alike. An unmarked clip would misrepresent the evidence.
        prs = [_pr(15, "T", "b",
                   comments=[("u", "x" * 2000) for _ in range(50)])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:15")
        self.assertLessEqual(len(text), ingest._REF_DETAIL_MAX_CHARS + 40)
        self.assertIn("truncated", text)

    def test_the_description_still_comes_first(self):
        # Retrieval and the writer both see the head of a chunk first; the
        # discussion must extend the description, never displace it.
        prs = [_pr(16, "The title", "The description.",
                   comments=[("u", "a comment")])]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:16")
        self.assertLess(text.index("The description."), text.index("a comment"))
        self.assertTrue(text.startswith("PR #16: The title"))

    def test_a_pr_with_no_discussion_is_unchanged(self):
        # The commonest PR in any repo. It must not gain empty section
        # headers -- they would dilute BM25's idf corpus-wide.
        prs = [_pr(17, "T", "Just a body.", state="OPEN", merged_at=None)]
        with mock.patch.object(ingest, "_gh_json", return_value=prs):
            chunks, _ = ingest.fetch_prs("r/r")
        text = _text_for(chunks, "pr:17")
        self.assertNotIn("Comment", text)
        self.assertNotIn("Review by", text)
        self.assertNotIn("Files changed", text)

    def test_missing_fields_do_not_crash(self):
        # An older gh, a GHES instance, or a permission that hides a field
        # returns it absent or null. Ingest must degrade, never fail.
        with mock.patch.object(ingest, "_gh_json",
                               return_value=[{"number": 18, "title": "T", "body": None}]):
            chunks, _ = ingest.fetch_prs("r/r")
        self.assertEqual(chunks[0]["ref"], "pr:18")
        self.assertIn("PR #18: T", chunks[0]["text"])


if __name__ == "__main__":
    unittest.main()


class CapsAndDisclosureTests(unittest.TestCase):
    """The caps were the biggest violation of "if it exists in the repo, it can
    be answered": psf/requests has 3,087 PRs and 4,167 issues, and 200/500 meant
    90% of its recorded discussion was invisible to search.

    Raising them is only half the job. A cap that IS hit must be DISCLOSED --
    an "honest unknown" about something sitting in PR #4000 of an index that
    stopped at #3000 is a lie of omission, and indistinguishable from a real one
    unless the partial index is declared."""

    def test_the_caps_cover_a_real_large_repo(self):
        # psf/requests, measured 2026-07-28: 3,087 PRs / 4,167 issues.
        self.assertGreaterEqual(ingest.PR_LIMIT, 3087)
        self.assertGreaterEqual(ingest.ISSUE_LIMIT, 4167)

    def test_bulk_list_calls_get_their_own_timeout(self):
        # ~13 PRs/sec measured with the full field set, so a 3,000-PR repo needs
        # ~4 minutes -- the 120s per-call timeout would kill it long before the
        # cap ever mattered. The caps were never the only thing in the way.
        self.assertGreater(ingest._LIST_TIMEOUT, ingest._SUBPROCESS_TIMEOUT)
        self.assertGreaterEqual(ingest._LIST_TIMEOUT, ingest.PR_LIMIT / 13)

    def test_fetch_prs_uses_the_long_timeout(self):
        seen = {}

        def fake(args, token=None, timeout=None):
            seen["timeout"] = timeout
            return []

        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            ingest.fetch_prs("o/r")
        self.assertEqual(seen["timeout"], ingest._LIST_TIMEOUT)

    def test_hitting_the_pr_cap_is_disclosed(self):
        stats = {}
        full = [_pr(i, "T", "b") for i in range(ingest.PR_LIMIT)]
        with mock.patch.object(ingest, "_gh_json", return_value=full):
            ingest.fetch_prs("o/r", stats=stats)
        self.assertTrue(stats.get("truncated"),
                        "a partial PR index must never read as complete")

    def test_not_hitting_the_cap_is_not_flagged(self):
        stats = {}
        with mock.patch.object(ingest, "_gh_json", return_value=[_pr(1, "T", "b")]):
            ingest.fetch_prs("o/r", stats=stats)
        self.assertFalse(stats.get("truncated"))

    def test_hitting_the_issue_cap_is_disclosed(self):
        stats = {}
        full = [{"number": i} for i in range(ingest.ISSUE_LIMIT)]
        with mock.patch.object(ingest, "_gh_json", return_value=full):
            ingest.fetch_all_issue_ids("o/r", stats=stats)
        self.assertTrue(stats.get("truncated"))

    def test_a_pr_cap_hit_reaches_meta_json(self):
        # End to end: the flag has to survive into the corpus provenance, which
        # is what /status and the app's partial-index banner read.
        import tempfile
        from pathlib import Path
        from evals.corpus_meta import load_meta
        full = ([{"ref": f"pr:{i}", "source": "pr", "text": "t"} for i in range(3)],
                set())
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs",
                                  side_effect=lambda r, token=None, stats=None: (
                                      stats.__setitem__("truncated", True), full)[1]), \
                mock.patch.object(ingest, "fetch_all_issue_ids", return_value=set()), \
                mock.patch.object(ingest, "fetch_commits", return_value=[]), \
                mock.patch.object(ingest, "fetch_issues", return_value=[]), \
                mock.patch.object(ingest, "fetch_code", return_value=[]):
            ingest.ingest_repo("o/r", d, commit="abc", code_dir=".")
            self.assertTrue(load_meta(Path(d) / "meta.json")["truncated"])


class DepthPassIsBestEffortTests(unittest.TestCase):
    """Coverage is the bar; the discussion is an enhancement on top of it — so
    the depth pass must never be able to fail an ingest.

    Before this it could, and did: `simonw/sqlite-utils` failed its ENTIRE
    connect with `stream error: stream ID 3; CANCEL; received from peer` at
    limit 400, taking the successful coverage pass down with it (found live
    2026-07-28, after the two-pass design shipped). DISCUSSION_DEPTH cannot be
    one safe number — cost tracks how CHATTY a repo's items are, not how many
    exist, so 400 is fine on psf/requests and unaffordable on sqlite-utils."""

    def _gh(self, depth_behaviour):
        """Coverage always succeeds; the depth call does whatever is asked."""
        seen = []

        def fake(args, token=None, timeout=None):
            limit = int(args[args.index("--limit") + 1])
            fields = args[args.index("--json") + 1]
            if "comments" not in fields:
                return [_pr(1, "T", "b"), _pr(2, "T", "b")]      # coverage pass
            seen.append(limit)
            return depth_behaviour(limit)
        return fake, seen

    def test_a_failing_depth_pass_still_yields_full_coverage(self):
        def always_fail(limit):
            raise subprocess.CalledProcessError(1, "gh", stderr="stream error: CANCEL")

        fake, seen = self._gh(always_fail)
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            chunks, _ = ingest.fetch_prs("simonw/sqlite-utils")
        self.assertEqual({c["ref"] for c in chunks}, {"pr:1", "pr:2"},
                         "every PR must still be indexed by its description")

    def test_it_shrinks_and_retries_rather_than_giving_up_at_once(self):
        def always_fail(limit):
            raise subprocess.CalledProcessError(1, "gh", stderr="boom")

        fake, seen = self._gh(always_fail)
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            ingest.fetch_prs("o/r")
        self.assertGreater(len(seen), 1, "must retry smaller before giving up")
        self.assertEqual(seen, sorted(seen, reverse=True), "each retry must be smaller")
        self.assertGreaterEqual(seen[-1], ingest._MIN_DISCUSSION_DEPTH // 2)

    def test_a_smaller_limit_that_succeeds_is_used(self):
        def fail_above_100(limit):
            if limit > 100:
                raise subprocess.CalledProcessError(1, "gh", stderr="too chatty")
            return [_pr(1, "T", "b", comments=[("dev", "the real reason")])]

        fake, seen = self._gh(fail_above_100)
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            chunks, _ = ingest.fetch_prs("o/r")
        self.assertIn("the real reason", _text_for(chunks, "pr:1"),
                      "a depth pass that succeeded smaller must still be applied")

    def test_a_timeout_is_handled_like_a_failure_not_a_crash(self):
        def times_out(limit):
            raise subprocess.TimeoutExpired("gh", 900)

        fake, _ = self._gh(times_out)
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            chunks, _ = ingest.fetch_prs("o/r")
        self.assertEqual(len(chunks), 2)

    def test_the_recorded_depth_reflects_what_actually_landed(self):
        def always_fail(limit):
            raise subprocess.CalledProcessError(1, "gh", stderr="boom")

        stats = {}
        fake, _ = self._gh(always_fail)
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            ingest.fetch_prs("o/r", stats=stats)
        self.assertEqual(stats["discussion_depth"], 0,
                         "claiming depth that was never fetched would be a false claim")
