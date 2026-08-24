# evals/test_rejection_conflation.py
"""`rejected_attempts` calls an auto-close a refusal, and the successor that
proves otherwise is sitting in the same evidence.

THE RECORDED CASE (2026-08-24, live, `SaravananJaichandar/world-model-mcp`
@ `5ec7fc6`; docs/experiments/2026-08-24-agent-mode-matched-pair-results.md).
Asked about `pr:23`, the answer's PROSE was exactly right:

    "It was not merged, as it was auto-closed and replaced by PR 24."

and `rests_on_unlanded: true` fired correctly. Meanwhile the structured
`rejected_attempts` field in the same payload listed:

    [{"ref": "pr:23", "title": "v0.12.3: universal content-type routing consumers"}]

A client renders the FIELD. So the payload simultaneously told a reader "this was
replaced and shipped" in prose and "somebody tried this and it was refused" in
the data. `pr:23` was auto-closed by GitHub when its base branch `#22` merged and
was deleted; the work landed verbatim as `#24`.

THIS IS NOT A BUG IN THE PARSER. `evals/attempts.py` documents exactly what it
does -- "closed WITHOUT being merged" -- and `pr:23` is precisely that. The
parser is correct against its own contract. The defect is that the contract and
the NAME have drifted apart: the field is called `rejected_attempts`, and the MCP
tool description sells it as "pull requests already tried and REFUSED". Reported
WHAT was closed; consumed as WHAT was refused.

Already measured, in [[Agent Mode]] and the 2026-08-14 meilisearch dogfood: of 11
closed-unmerged PRs on a real repo only 2 carried `changes_requested`, and across
C2's nine closed PRs only ONE was an approach genuinely not adopted. This file
turns that statistic into a named, committed case.

WHY IT IS FIXABLE, AND WHY THAT MATTERS. The disqualifying evidence is already
in the evidence map: `pr:24` is MERGED and its own indexed text says "Replaces
#23". No model, no extra fetch, no review-thread reading -- the thing
`evals/attempts.py` deliberately refuses to do. A successor check is a different
shape from judging WHY something closed, and it stays inside the module's
"the indexed TEXT has to say it" rule.

STATUS: FIXED 2026-08-24. `evals.attempts._superseded_numbers` now drops a
closed pull request that a MERGED one says it replaces. The characterization
below was inverted at that moment rather than deleted, so this file still reads
as the record of a real defect and its fix.

WHAT THIS FILE DOES. Pins the conflation, proves the disqualifying signal is
computable, and -- most importantly -- pins the things the fix must NOT break:
a genuinely refused PR must still be reported, and `unlanded_prs` must keep
flagging `pr:23`, because it is genuinely unlanded and that predicate is RIGHT.
`_superseded_by` lives here in the test, not in the brain.
"""
import json
import re
import unittest
from pathlib import Path

from .attempts import rejected_attempts, unlanded_prs

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "conflation" / "wmm_pr23_pr24.jsonl"

AUTO_CLOSED = "pr:23"      # CLOSED, never merged, superseded by pr:24
SUCCESSOR = "pr:24"        # MERGED, and says so in its own body

# A genuinely refused pull request, in ingest's real shape. Hand-built on
# purpose: the point is that a fix must keep reporting THIS while dropping
# pr:23, so it must not come from the same repo's happenstance.
# NOTE the shape: `review:` sits INSIDE the state-header bracket line, which is
# where evals/ingest.py:640 writes it and the only place _review_decision reads
# it. The first draft of this fixture used a free-standing "Review:" paragraph
# and the review key came back None -- the forgery defence working exactly as
# designed, caught by its own test fixture being wrong.
GENUINELY_REFUSED = (
    "PR #77: Replace the audit chain with a plain timestamp column\n\n"
    "[CLOSED by contributor] review: changes_requested\n\n"
    "Maintainer asked for this not to land in this form."
)


def _evidence():
    rows = [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]
    return {r["ref"]: r["text"] for r in rows}


def _superseded_by(ref, evidence):
    """Is there a MERGED pull request in `evidence` whose own text says it
    replaces/supersedes `ref`?

    The candidate signal, kept in the test. Deliberately narrow: it requires the
    successor to be present, to be MERGED per its own indexed header, and to name
    the number explicitly. It reports WHAT the text says, never why anything
    closed -- the line evals/attempts.py draws and this must not cross.
    """
    n = ref.split(":", 1)[1] if ":" in ref else ref
    pattern = re.compile(rf"\b(?:replaces|supersedes)\s+#{re.escape(n)}\b", re.I)
    for other, text in (evidence or {}).items():
        if other == ref or not other.startswith("pr:") or not isinstance(text, str):
            continue
        header = next((l for l in text.split("\n")[:6] if l.startswith("[")), "")
        if header.startswith("[MERGED") and pattern.search(text):
            return other
    return None


class TheRecordedCase(unittest.TestCase):
    """Always-run, offline. Pins the fixture so the board cannot drift off the
    case it claims to describe."""

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                       # pragma: no cover
            raise unittest.SkipTest("conflation fixture missing")
        cls.evidence = _evidence()

    def test_the_fixture_holds_both_pull_requests_in_the_recorded_states(self):
        self.assertIn(AUTO_CLOSED, self.evidence)
        self.assertIn(SUCCESSOR, self.evidence)
        self.assertIn("[CLOSED", self.evidence[AUTO_CLOSED])
        self.assertIn("[MERGED", self.evidence[SUCCESSOR])

    def test_the_successor_names_the_auto_closed_pr_in_its_own_text(self):
        """The whole fix rests on this being in the INDEXED text rather than
        needing a fetch or a review thread."""
        self.assertRegex(self.evidence[SUCCESSOR], r"(?i)replaces\s+#23")


class ConflationIsReproduced(unittest.TestCase):
    """Always-run, offline. The defect itself, on real committed evidence."""

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                       # pragma: no cover
            raise unittest.SkipTest("conflation fixture missing")
        cls.evidence = _evidence()

    def test_an_auto_closed_pr_is_no_longer_a_rejected_attempt(self):
        """FLIPPED 2026-08-24, deliberately, when the successor check shipped in
        `evals.attempts._superseded_numbers`. This assertion was the inverse and
        was green because the defect was present; it is the red->green half of
        this board and the experiment record says so."""
        refs = [a["ref"] for a in rejected_attempts(self.evidence)]
        self.assertNotIn(
            AUTO_CLOSED, refs,
            "pr:23 is being reported as REFUSED again -- the successor check has "
            "regressed. pr:24 is merged and its body says it replaces #23.")

    def test_the_disqualifying_signal_is_computable_from_the_same_evidence(self):
        """What a fix would key on: no model, no extra request, and it never
        asks WHY anything was closed."""
        self.assertEqual(_superseded_by(AUTO_CLOSED, self.evidence), SUCCESSOR)


class WhatAFixMustNotBreak(unittest.TestCase):
    """Always-run, offline. These must stay green THROUGH the fix. A successor
    check that also silences real refusals, or that disturbs the unlanded
    predicate, is a worse product than the conflation it removes."""

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                       # pragma: no cover
            raise unittest.SkipTest("conflation fixture missing")
        cls.evidence = _evidence()

    def test_a_genuinely_refused_pr_is_still_reported(self):
        ev = dict(self.evidence, **{"pr:77": GENUINELY_REFUSED})
        refs = [a["ref"] for a in rejected_attempts(ev)]
        self.assertIn("pr:77", refs, "a real refusal must survive any fix here")

    def test_no_successor_claims_the_genuinely_refused_pr(self):
        ev = dict(self.evidence, **{"pr:77": GENUINELY_REFUSED})
        self.assertIsNone(_superseded_by("pr:77", ev))

    def test_without_the_successor_in_evidence_the_attempt_is_still_reported(self):
        """Absence of a successor is NOT evidence of refusal -- but it is also
        not evidence of replacement. With pr:24 out of the evidence there is
        nothing to disqualify pr:23, so it must come back."""
        ev = {k: v for k, v in self.evidence.items() if k != SUCCESSOR}
        self.assertIn(AUTO_CLOSED, [a["ref"] for a in rejected_attempts(ev)])

    def test_an_unmerged_pr_claiming_to_replace_another_suppresses_nothing(self):
        """The forgery bound. Body text is author-controlled, so the claim is
        honoured only from a MERGED pull request. Anyone can OPEN one saying
        'Replaces #23'; getting it merged needs write access."""
        ev = {k: v for k, v in self.evidence.items() if k != SUCCESSOR}
        ev["pr:98"] = ("PR #98: sneak\n\n[OPEN by drive-by]\n\nReplaces #23.")
        self.assertIn(AUTO_CLOSED, [a["ref"] for a in rejected_attempts(ev)])

    def test_a_longer_number_does_not_match_by_prefix(self):
        """`Replaces #234` must not suppress pr:23."""
        ev = {k: v for k, v in self.evidence.items() if k != SUCCESSOR}
        ev["pr:97"] = ("PR #97: other\n\n[MERGED by maintainer]\n\nReplaces #234.")
        self.assertIn(AUTO_CLOSED, [a["ref"] for a in rejected_attempts(ev)])

    def test_review_decision_is_absent_rather_than_defaulted(self):
        """pr:23 carries no reviewDecision, so it must carry no `review` key --
        an absent key is the only representation of unknown a caller cannot
        mistake for an answer (evals/attempts.py's own rule).

        Asserted with the successor held OUT of evidence, since pr:23 is
        correctly suppressed when pr:24 is present. The property under test is
        the review key, not the suppression, and it needs the entry to exist."""
        ev = {k: v for k, v in self.evidence.items() if k != SUCCESSOR}
        entry = next(a for a in rejected_attempts(ev) if a["ref"] == AUTO_CLOSED)
        self.assertNotIn("review", entry)

    def test_the_genuinely_refused_pr_keeps_its_review_decision(self):
        """The other half: a real `changes_requested` must survive the fix with
        its value intact, not just its ref."""
        ev = dict(self.evidence, **{"pr:77": GENUINELY_REFUSED})
        entry = next(a for a in rejected_attempts(ev) if a["ref"] == "pr:77")
        self.assertEqual(entry.get("review"), "changes_requested")

    def test_unlanded_prs_is_RIGHT_about_the_auto_closed_pr(self):
        """The distinction that keeps a fix aimed at the correct module. pr:23
        genuinely never landed, so `rests_on_unlanded` firing on a claim citing
        it was CORRECT in the recorded run. The defect is the word 'rejected',
        not the word 'unlanded', and nothing here should change that."""
        self.assertIn(AUTO_CLOSED, unlanded_prs(self.evidence))
        self.assertNotIn(SUCCESSOR, unlanded_prs(self.evidence))
