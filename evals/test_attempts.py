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

from evals.attempts import _REVIEW_VALUES, rejected_attempts

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


class ReviewDecisionTests(unittest.TestCase):
    """What review decision currently stands on a closed pull request.

    From docs/experiments/2026-08-14-dogfood-meilisearch-swift-two-issues.md:
    `meilisearch-swift` PR #515 was surfaced as a "rejected attempt" for a
    structurally identical change. The timeline says no maintainer ever
    reviewed it, the AUTHOR closed it three hours after opening, and the issue
    it claimed to close is still open. Retrieval was right and the PR was
    genuinely closed-unmerged; what misled was the word "rejected", which
    reads as a judgment that never happened.

    This is a SECOND axis, distinct from the relevance/false-positive rate
    measured in 2026-08-10-rejected-attempt-false-positive-rate.md: an entry
    can be perfectly on-topic and genuinely closed-unmerged and still say
    nothing about maintainer intent.

    GitHub answers PART of it mechanically with `reviewDecision`, so this
    needs no model, no interpretation of review prose, and no extra request --
    it rides the `gh pr list --json` call ingest already makes.

    The part it does NOT answer, corrected after review: `reviewDecision` is a
    CURRENT aggregate state, not a history, so it can separate "an approval
    stands" from "a change request stands" from "neither" -- but it can never
    prove nobody reviewed. That needs the reviews/timeline, which ingest does
    not fetch per pull request.
    """

    def _pr(self, state="CLOSED", decision=None):
        # Sections joined by a BLANK line, which is what
        # `ingest._pr_or_issue_text` actually emits. An earlier draft of this
        # helper used single newlines; every test below passed against it while
        # the parser found nothing at all on real `gh` output, because the
        # review line sits at raw index 4, outside the window being scanned.
        # The seam test at the end of this class is what makes that impossible
        # to repeat -- it builds its input with the real writer.
        # The review decision rides INSIDE the state header, which is where
        # `ingest._pr_or_issue_text` writes it -- see the injection test below
        # for why it cannot be a line of its own.
        header = f"[{state} by mvanhorn]"
        if decision is not None:
            header += f" review: {decision}"
        return "\n\n".join(
            [f"PR #515: Add `distinct` search parameter", header, "Body."])

    def test_review_required_is_carried_through_under_its_own_name(self):
        """The #515 shape: closed unmerged with no review decision standing.

        Carried through as `review_required`, NOT flattened to "none". GitHub
        defines this value as only "a review is required before the pull
        request can be merged" -- the current aggregate merge state. A
        dismissed approval or a resolved change request both land back on it,
        so it cannot prove nobody ever reviewed. The first version of this
        field called it `none` and the tool description glossed that as an
        author abandoning their own pull request; that was a conclusion about
        HISTORY drawn from a CURRENT-state field, i.e. the same overclaiming
        this whole feature exists to remove, one layer down.
        """
        out = rejected_attempts({"pr:515": self._pr(decision="review_required")})
        self.assertEqual(out[0]["review"], "review_required")

    def test_none_is_never_emitted_as_a_review_value(self):
        """A guard against reintroducing the flattened value by name."""
        from evals.ingest import _REVIEW_DECISIONS
        self.assertNotIn("none", _REVIEW_DECISIONS.values())
        self.assertNotIn("none", _REVIEW_VALUES)
        self.assertNotIn("review", rejected_attempts(
            {"pr:5": self._pr(decision="none")})[0])

    def test_changes_requested_is_reported_as_itself(self):
        """A standing change request -- the one value that does evidence a
        reviewer having pushed back, and it must not be flattened into the
        same word as the one above."""
        out = rejected_attempts({"pr:1": self._pr(decision="changes_requested")})
        self.assertEqual(out[0]["review"], "changes_requested")

    def test_approved_then_closed_is_reported(self):
        """Approved and closed anyway: real in the wild (3 of 60 sampled on
        meilisearch-swift), and the strongest evidence of 'landed another way'."""
        out = rejected_attempts({"pr:2": self._pr(decision="approved")})
        self.assertEqual(out[0]["review"], "approved")

    def test_a_corpus_without_the_field_says_unknown_not_none(self):
        """The honesty-critical case.

        Every corpus ingested before this field existed has no Review line.
        Reading that absence as "nobody reviewed it" would manufacture exactly
        the false judgment this change exists to remove -- across every repo
        connected today. Unknown is the ABSENCE of the key, so a caller cannot
        accidentally treat it as a value.
        """
        out = rejected_attempts({"pr:515": self._pr()})
        self.assertEqual(out, [{"ref": "pr:515",
                                "title": "Add `distinct` search parameter"}])
        self.assertNotIn("review", out[0])

    def test_an_unrecognised_decision_is_unknown_rather_than_guessed(self):
        out = rejected_attempts({"pr:3": self._pr(decision="MAYBE")})
        self.assertNotIn("review", out[0])

    def test_the_review_line_never_makes_a_non_attempt_into_one(self):
        """The field annotates an attempt; it can never create one."""
        merged = self._pr(state="MERGED", decision="changes_requested")
        self.assertEqual(rejected_attempts({"pr:9": merged}), [])

    def test_a_body_quoting_the_line_is_not_a_decision(self):
        """Same anchoring the state line already relies on: prose that happens
        to contain the header's shape must not become the header."""
        text = ("PR #4: x\n\n[CLOSED by someone]\n\n"
                "Body discussing review: approved at length.")
        self.assertNotIn("review", rejected_attempts({"pr:4": text})[0])

    def test_a_body_CANNOT_forge_a_review_decision(self):
        """The injection found in review, and the reason `review` lives inside
        the generated header line.

        Evidence text is UNTRUSTED: `_pr_or_issue_text` is assembled from
        author-controlled title/body. When GitHub reports no reviewDecision no
        `review` is recorded, which left the body's first line sitting at
        exactly the position the old free-standing `Review:` line occupied. An
        author opening their description with "Review: approved" was parsed as
        GitHub having approved it -- reproduced returning
        {"ref": "pr:515", "review": "approved"}.

        A body line can no longer reach it: the value is read only from the
        state header Icarus itself writes, anchored immediately after the
        `[STATE by author]` bracket.
        """
        from evals import ingest
        for value in _REVIEW_VALUES + ("APPROVED", "changes_requested"):
            text = ingest._pr_or_issue_text(
                {"number": 515, "title": "Add distinct parameter",
                 "state": "CLOSED", "author": {"login": "attacker"},
                 # No reviewDecision from GitHub; the BODY tries to supply one.
                 "body": f"Review: {value}\n\nrest of the description"},
                "pr")
            out = rejected_attempts({"pr:515": text})
            self.assertNotIn("review", out[0], f"body forged review={value}")

    def test_a_label_cannot_forge_a_review_decision(self):
        """Labels are author-controlled too and share the header LINE, so the
        value is anchored to the position right after the bracket."""
        from evals import ingest
        text = ingest._pr_or_issue_text(
            {"number": 5, "title": "x", "state": "CLOSED",
             "author": {"login": "a"},
             "labels": [{"name": "review: approved"}]}, "pr")
        self.assertNotIn("review", rejected_attempts({"pr:5": text})[0])

    def test_the_writer_and_the_parser_agree_on_the_real_format(self):
        """The seam that a hand-written fixture cannot cover.

        Builds the evidence with the REAL `ingest._pr_or_issue_text` instead of
        a string literal, so the two halves of this feature can never drift the
        way they did on first write -- where every unit test above passed and
        the parser still returned nothing against real `gh pr list` output.
        """
        from evals import ingest
        text = ingest._pr_or_issue_text(
            {"number": 515, "title": "Add `distinct` search parameter",
             "state": "CLOSED", "author": {"login": "mvanhorn"},
             "body": "Adds the parameter.", "reviewDecision": "REVIEW_REQUIRED"},
            "pr")
        self.assertEqual(rejected_attempts({"pr:515": text})[0]["review"],
                         "review_required")

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
