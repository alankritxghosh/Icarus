"""`rejected_attempts` — what was tried and refused.

Weighted toward what must NOT be reported: a closed ISSUE is not a rejected
attempt, a MERGED pull request is not one, and nothing may be inferred from a
ref whose indexed text does not say it.

Stdlib only, no model, no network. Includes a guard against the REAL committed
corpus so the parser cannot drift from what ingest actually writes.
"""
import json
import os
import unittest

from evals.attempts import rejected_attempts

CLOSED_PR = "PR #20754: Clean up stale Python temp dirs\n[CLOSED by someone]\nBody."
MERGED_PR = "PR #20752: allow temp_dir to clean up on drop\n[MERGED by simonw]\nBody."
OPEN_PR = "PR #1596: Fix Anthropic API key alias\n[OPEN by someone]\nBody."
CLOSED_ISSUE = "ISSUE #1: Initial design\n[CLOSED by simonw] labels: enhancement\nBody."


class RejectedAttemptsTests(unittest.TestCase):

    def test_reports_a_closed_pull_request(self):
        out = rejected_attempts({"pr:20754": CLOSED_PR})
        self.assertEqual(out, [{"ref": "pr:20754",
                                "title": "Clean up stale Python temp dirs"}])

    def test_merged_pull_request_is_not_an_attempt(self):
        """A merged PR is in the commit graph already -- reporting it as a
        refusal would invert the entire signal."""
        self.assertEqual(rejected_attempts({"pr:20752": MERGED_PR}), [])

    def test_open_pull_request_is_not_an_attempt(self):
        self.assertEqual(rejected_attempts({"pr:1596": OPEN_PR}), [])

    def test_closed_issue_is_not_an_attempt(self):
        """The decoy that matters: 544 closed issues vs 129 closed PRs in the
        committed corpus, so counting issues would bury the signal."""
        self.assertEqual(rejected_attempts({"issue:1": CLOSED_ISSUE}), [])

    def test_code_and_commit_refs_are_ignored(self):
        ev = {"code:a.py#L1-L5": "[CLOSED by nobody]\nx",
              "commit:abc123": "[CLOSED by nobody]\nx",
              "doc:README.md": "[CLOSED by nobody]\nx"}
        self.assertEqual(rejected_attempts(ev), [])

    def test_no_header_is_skipped_not_guessed(self):
        self.assertEqual(rejected_attempts({"pr:9": "PR #9: no header line\nbody"}), [])

    def test_state_must_be_at_the_header_start(self):
        """A body merely CONTAINING the word must not trip it -- the same
        anchored-match discipline demo/entry_points.py learned the hard way."""
        text = "PR #9: title\n[MERGED by x]\nThis reverts a [CLOSED by y] attempt."
        self.assertEqual(rejected_attempts({"pr:9": text}), [])

    def test_missing_title_is_empty_not_invented(self):
        out = rejected_attempts({"pr:9": "PR #9\n[CLOSED by x]\nbody"})
        self.assertEqual(out, [{"ref": "pr:9", "title": ""}])

    def test_order_mirrors_input_and_is_deterministic(self):
        ev = {"pr:3": CLOSED_PR.replace("#20754", "#3"),
              "pr:1": CLOSED_PR.replace("#20754", "#1"),
              "pr:2": MERGED_PR}
        self.assertEqual([r["ref"] for r in rejected_attempts(ev)], ["pr:3", "pr:1"])

    def test_empty_and_hostile_input_never_raises(self):
        for ev in ({}, None, {"pr:1": None}, {None: "x"}, {"pr:1": 3}):
            self.assertEqual(rejected_attempts(ev), [])


class RealCorpusFormatTests(unittest.TestCase):
    """The parser must match what `evals/ingest` ACTUALLY writes, not what this
    test file imagines. Reads the committed corpus rather than a fixture, so a
    change to the header format fails here instead of silently emptying the
    signal in production."""

    CORPUS = "evals/corpus/chunks.jsonl"

    def setUp(self):
        if not os.path.exists(self.CORPUS):
            self.skipTest("committed corpus not present")

    def test_finds_real_closed_prs_and_no_merged_or_issues(self):
        evidence = {}
        with open(self.CORPUS) as fh:
            for line in fh:
                c = json.loads(line)
                if c.get("source") in ("pr", "issue"):
                    evidence[c["ref"]] = c["text"]
        out = rejected_attempts(evidence)
        refs = {r["ref"] for r in out}

        self.assertTrue(refs, "expected some closed PRs in the real corpus")
        # Every hit is a pr: ref whose text really says CLOSED.
        for r in out:
            self.assertTrue(r["ref"].startswith("pr:"))
            self.assertIn("[CLOSED by", evidence[r["ref"]])
        # And nothing merged or issue-shaped leaked in.
        for ref, text in evidence.items():
            if ref.startswith("issue:") or "[MERGED by" in text:
                self.assertNotIn(ref, refs)


if __name__ == "__main__":
    unittest.main()
