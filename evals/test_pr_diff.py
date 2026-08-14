# evals/test_pr_diff.py
"""`fetch_pr_diff` and the `diff:` source it introduces. Offline: subprocess and
the gh call are stubbed, so nothing here touches the network.

The honesty property worth stating plainly: a diff shows what the code BECAME
and never why anyone chose it. So `diff:` is a known source (its citations
resolve like any other) but deliberately NOT a rationale source -- a "why"
grounded only on a diff must still abstain.
"""

import json
import subprocess
import unittest
from unittest import mock

from . import ingest
from .gate import _RATIONALE_MARKERS, _source, gate
from .investigation import _RATIONALE_SOURCES
from demo.links import ref_to_url

DIFF = ("diff --git a/llm/cli.py b/llm/cli.py\n"
        "@@ -10,7 +10,7 @@\n-WINDOW = 100\n+WINDOW = 300\n")


class FetchPrDiffTests(unittest.TestCase):
    def _run(self, stdout=DIFF, side_effect=None):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)
        with mock.patch.object(ingest.subprocess, "run",
                               side_effect=side_effect,
                               return_value=completed) as run:
            return ingest.fetch_pr_diff("owner/repo", 400, token="gho_secret"), run

    def test_it_returns_the_real_hunks_as_one_chunk(self):
        chunk, _run = self._run()
        self.assertEqual(chunk.ref, "diff:400")
        self.assertEqual(chunk.source, "diff")
        self.assertIn("+WINDOW = 300", chunk.text)

    def test_the_token_never_reaches_argv(self):
        # The same leak-safe contract every other gh call here holds: the token
        # rides in the subprocess ENV, never the command line, never a log.
        _chunk, run = self._run()
        argv = run.call_args.args[0]
        self.assertNotIn("gho_secret", " ".join(argv))
        self.assertEqual(argv[:4], ["gh", "pr", "diff", "400"])
        self.assertIn("GH_TOKEN", run.call_args.kwargs["env"])

    def test_an_enormous_diff_is_truncated_WITH_a_visible_marker(self):
        chunk, _run = self._run(stdout="x" * (ingest._DIFF_MAX_CHARS + 5000))
        self.assertIn("[diff truncated]", chunk.text)
        self.assertLess(len(chunk.text), ingest._DIFF_MAX_CHARS + 200)

    def test_an_empty_diff_is_nothing_rather_than_an_empty_chunk(self):
        chunk, _run = self._run(stdout="   \n")
        self.assertIsNone(chunk)

    def test_every_failure_mode_fails_safe_to_None(self):
        for error in (subprocess.CalledProcessError(1, "gh"),
                      subprocess.TimeoutExpired("gh", 1)):
            chunk, _run = self._run(side_effect=error)
            self.assertIsNone(chunk, error)


class DiffSourceTests(unittest.TestCase):
    def test_a_diff_citation_resolves_like_any_other_ref(self):
        self.assertEqual(_source("diff:400"), "diff")
        result = gate(json.dumps({"verdict": "answer",
                                  "answer": "It raised the window to 300.",
                                  "citations": ["diff:400"]}),
                      ["diff:400"])
        self.assertEqual(result.verdict, "answer")
        self.assertEqual(result.citations, ["diff:400"])

    def test_a_diff_links_to_the_pull_requests_files_view(self):
        self.assertEqual(ref_to_url("diff:400", "owner/repo", "abc123"),
                         "https://github.com/owner/repo/pull/400/files")

    def test_a_diff_is_NOT_recorded_rationale(self):
        # It shows what the code became. It never records why anyone chose it,
        # so a "why" resting only on a diff must still be an honest unknown.
        self.assertNotIn("diff", _RATIONALE_SOURCES)
        result = gate(json.dumps({"verdict": "answer",
                                  "answer": "It was raised for scalability.",
                                  "citations": ["diff:400"]}),
                      ["diff:400"],
                      question="why was the window raised to 300?",
                      evidence={"diff:400": DIFF})
        self.assertEqual(result.verdict, "unknown")

    def test_the_marker_list_the_guard_uses_is_the_gates_real_one(self):
        # Pinned so this test cannot silently pass against a hand-copy.
        self.assertTrue(_RATIONALE_MARKERS)


class ReviewDecisionLineTests(unittest.TestCase):
    """`reviewDecision`, the second field ingest can get for free.

    Same shape as the linked-issue line above: already available on the
    `gh pr list --json` call ingest makes, previously not asked for. It is what
    lets `evals/attempts.py` say whether anyone actually reviewed a closed
    pull request instead of leaving every one of them under the word
    "rejected" (docs/experiments/2026-08-14-dogfood-*.md).
    """

    def test_each_github_decision_maps_to_one_recorded_word(self):
        for decision, expected in (("APPROVED", "approved"),
                                   ("CHANGES_REQUESTED", "changes_requested"),
                                   ("REVIEW_REQUIRED", "none")):
            text = ingest._pr_or_issue_text(
                {"number": 515, "title": "x", "state": "CLOSED",
                 "reviewDecision": decision}, "pr")
            self.assertIn(f"Review: {expected}", text)

    def test_a_missing_or_null_decision_writes_no_line_at_all(self):
        """Unknown must stay unknown. GitHub returns null here for reasons that
        are not "nobody looked" (measured: 1 of 60 sampled PRs), and every
        corpus ingested before this field existed has no value at all."""
        for data in ({"number": 1, "title": "x", "state": "CLOSED"},
                     {"number": 1, "title": "x", "state": "CLOSED",
                      "reviewDecision": None},
                     {"number": 1, "title": "x", "state": "CLOSED",
                      "reviewDecision": ""}):
            self.assertNotIn("Review:", ingest._pr_or_issue_text(data, "pr"))

    def test_an_issue_never_gets_a_review_line(self):
        text = ingest._pr_or_issue_text(
            {"number": 1, "title": "x", "state": "CLOSED",
             "reviewDecision": "APPROVED"}, "issue")
        self.assertNotIn("Review:", text)

    def test_a_pull_request_without_the_field_is_byte_identical_to_before(self):
        # The committed corpus depends on this, exactly as the linked-issue
        # line below does.
        data = {"number": 400, "title": "chunking", "body": "Body.",
                "state": "CLOSED"}
        self.assertEqual(
            ingest._pr_or_issue_text({**data, "reviewDecision": None}, "pr"),
            ingest._pr_or_issue_text(data, "pr"))

    def test_the_field_is_actually_requested_from_github(self):
        # Writing the line is useless if nothing ever asks for the value; this
        # is the seam where the linked-issue equivalent sat unfetched for
        # months. Base pass, so it covers every PR, not just the depth pass.
        self.assertIn("reviewDecision", ingest._PR_FIELDS_BASE)


class LinkedIssueLineTests(unittest.TestCase):
    """GitHub's own closing-issue links, which ingest fetched and discarded."""

    def test_closing_references_are_recorded_as_ordinary_mentions(self):
        text = ingest._pr_or_issue_text(
            {"number": 400, "title": "chunking", "body": "Body.",
             "closingIssuesReferences": [{"number": 1523}, {"number": 99}]}, "pr")
        self.assertIn("Linked issues: #99, #1523", text)

    def test_a_pull_request_closing_nothing_is_byte_identical_to_before(self):
        # The committed corpus and every existing number depend on this: a PR
        # with no closing references must produce exactly the text it always did.
        data = {"number": 400, "title": "chunking", "body": "Body."}
        with_field = ingest._pr_or_issue_text({**data, "closingIssuesReferences": []}, "pr")
        without = ingest._pr_or_issue_text(data, "pr")
        self.assertEqual(with_field, without)
        self.assertNotIn("Linked issues", without)

    def test_the_line_makes_the_entity_index_see_the_link(self):
        # No new parser: the exact link is written in the shape the mention
        # regex already reads, so entities.py needs no change at all.
        from .corpus import Chunk
        from .entities import EDGE_LINKED_ISSUES, build_entity_index
        text = ingest._pr_or_issue_text(
            {"number": 400, "title": "x", "body": "No mention in prose.",
             "closingIssuesReferences": [{"number": 372}]}, "pr")
        idx = build_entity_index([
            Chunk(ref="pr:400", source="pr", text=text),
            Chunk(ref="issue:372", source="issue", text="ISSUE #372: x")])
        self.assertEqual(idx.targets("pr:400", EDGE_LINKED_ISSUES), ["issue:372"])


if __name__ == "__main__":
    unittest.main()
