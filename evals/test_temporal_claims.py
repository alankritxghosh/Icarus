# evals/test_temporal_claims.py
"""A decision resting on a DEFERRAL, where later merged work exists, is marked.

THE RECORDED CASE (2026-08-25; docs/experiments/2026-08-25-agent-mode-three-trial-
variance.md). `get_task_context` on `SaravananJaichandar/world-model-mcp` returned,
in 3 of 4 identical calls, at support `explicit`:

    "The retrieval consumers do not CURRENTLY have wiring for the new
     influence_state and expires_at schema fields, as this was deferred to
     follow-up patches."   -- citations: [pr:22]

`pr:22` really does say that. It carries a literal section `## Consumer wiring --
deferred`, saying the filter and sweep "land in follow-up patches" and that the
pattern "defers routing consumers to v0.12.3". Every word was true when written.

`pr:24` -- titled "v0.12.3: universal content-type routing consumers" -- then
MERGED. At the commit under test the consumers ARE wired. The citation resolves,
the gate passes, and the answer describes a repository that no longer exists.

WHY NO EXISTING GUARD CATCHES IT. Groundedness proves the citation is real.
`rests_on_unlanded` asks whether anything cited LANDED -- `pr:22` merged, so it
is silent, correctly. `rejected_attempts` asks whether something was refused --
nothing was. Every honesty mechanism in the repo is answering a different
question from "is this still true".

WHY THIS IS THE FIX AND MORE TRIALS ARE NOT. The instability was measured to
track evidence recording SUCCESSIVE STATES of one feature: a layered subject was
unstable across three trials while a flat control on the same corpus, same
retrieval regime, was identical. A steadier writer or a bigger N does not touch
that. Knowing time passed does.

WHAT THE CHECK DELIBERATELY DOES NOT DO. It never says the deferral was
RESOLVED. Deciding that `pr:24` delivered what `pr:22` deferred is a semantic
judgment, and this repo has repeatedly refused to fake those -- the same line
`rejected_attempts` draws by reporting WHAT was closed and never WHY. The flag
says: this claim is indexed to a moment, here is what merged after it, go look.
"""
import json
import unittest
from pathlib import Path

from .attempts import deferred_claims, unlanded_prs
from .context_package import build_context_package
from .investigation import Claim, EvidenceRef, Investigation
from .pipeline import Result

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "temporal" / "wmm_pr22_pr24.jsonl"

DEFERRING = "pr:22"   # MERGED, and defers consumer wiring to follow-up patches
LATER = "pr:24"       # MERGED, later-numbered, titled v0.12.3

RECORDED_DECISION = ("The retrieval consumers do not currently have wiring for the "
                     "new influence_state and expires_at schema fields, as this was "
                     "deferred to follow-up patches.")

_STRUCTURE = {"file_edges": [], "file_edge_evidence": [], "package_edges": [],
              "components": [], "most_depended_on_files": [],
              "unresolved_import_count": 0, "unanalysed_languages": []}


def _texts():
    return {json.loads(l)["ref"]: json.loads(l)["text"]
            for l in _CORPUS.read_text().splitlines() if l.strip()}


def _package(texts, citations=(DEFERRING,)):
    inv = Investigation(objective="wire a new evidence_type", question="wire a new evidence_type")
    for ref in texts:
        inv.evidence[ref] = EvidenceRef(ref=ref, source="pr", via="t1", states_reason=True)
    inv.claims = [Claim(id="c1", text=RECORDED_DECISION, citations=list(citations),
                        support="explicit", verified=True)]
    return build_context_package(inv, Result(verdict="answer", citations=list(citations)),
                                 _STRUCTURE, texts)


class TheFixtureIsTheRealCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                        # pragma: no cover
            raise unittest.SkipTest("temporal fixture missing")
        cls.texts = _texts()

    def test_the_deferral_is_in_pr22s_own_text(self):
        self.assertRegex(self.texts[DEFERRING], r"(?i)consumer wiring\s*[-–—]+\s*deferred")
        self.assertRegex(self.texts[DEFERRING], r"(?i)follow-up patches")

    def test_the_successor_merged_and_is_later(self):
        self.assertIn("[MERGED", self.texts[LATER])
        self.assertGreater(int(LATER.split(":")[1]), int(DEFERRING.split(":")[1]))

    def test_no_existing_guard_sees_it(self):
        """Why a new check was needed rather than widening an old one: `pr:22`
        MERGED, so the unlanded predicate is silent -- and correctly so."""
        self.assertNotIn(DEFERRING, unlanded_prs(self.texts))
        self.assertNotIn(LATER, unlanded_prs(self.texts))


class TheCheckItself(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                        # pragma: no cover
            raise unittest.SkipTest("temporal fixture missing")
        cls.texts = _texts()

    def test_the_deferring_pr_is_reported_with_what_came_later(self):
        out = deferred_claims(self.texts)
        self.assertIn(DEFERRING, out)
        self.assertEqual(out[DEFERRING]["later_merged"], [LATER])
        self.assertTrue(out[DEFERRING]["phrase"])

    def test_the_successor_count_is_reported_as_the_strength_indicator(self):
        """The real case has exactly ONE merged pull request after it, which is
        why the successor is identifiable. Measured over the committed 526-PR
        corpus the same check fires on `pr:14` with 154 merged PRs after it --
        true, ancient, and near-meaningless. The count is what lets a reader
        tell those two apart, so it is not optional."""
        out = deferred_claims(self.texts)
        self.assertEqual(out[DEFERRING]["later_merged_count"], 1)

    def test_the_named_successors_are_bounded_and_NEAREST_first(self):
        """Found by running the check over the whole corpus: an old deferral
        listed essentially every later merged pull request. Each true, the set
        worthless. Nearest-first and capped."""
        ev = {DEFERRING: self.texts[DEFERRING]}
        for n in (30, 40, 50, 60, 70):
            ev[f"pr:{n}"] = f"PR #{n}: later\n\n[MERGED by someone]\n\nBody."
        out = deferred_claims(ev)[DEFERRING]
        self.assertEqual(out["later_merged"], ["pr:30", "pr:40", "pr:50"])
        self.assertEqual(out["later_merged_count"], 5)

    def test_the_successor_is_not_itself_flagged(self):
        self.assertNotIn(LATER, deferred_claims(self.texts))

    def test_a_deferral_with_nothing_later_is_NOT_reported(self):
        """The conservatism that keeps this usable. Without later merged work
        there is no reason to think time moved, and a repo that says 'not yet'
        constantly would drown the signal."""
        self.assertEqual(deferred_claims({DEFERRING: self.texts[DEFERRING]}), {})

    def test_an_EARLIER_merged_pr_does_not_count_as_later(self):
        ev = {DEFERRING: self.texts[DEFERRING],
              "pr:9": "PR #9: earlier thing\n\n[MERGED by someone]\n\nBody."}
        self.assertEqual(deferred_claims(ev), {})

    def test_a_later_but_UNMERGED_pr_does_not_count(self):
        ev = {DEFERRING: self.texts[DEFERRING],
              "pr:99": "PR #99: proposed\n\n[OPEN by someone]\n\nBody."}
        self.assertEqual(deferred_claims(ev), {})

    def test_a_pr_with_no_deferral_language_is_never_flagged(self):
        ev = {"pr:5": "PR #5: ordinary change\n\n[MERGED by someone]\n\nAdds a thing.",
              "pr:6": "PR #6: another\n\n[MERGED by someone]\n\nAdds another."}
        self.assertEqual(deferred_claims(ev), {})

    def test_hostile_and_malformed_input_never_raises(self):
        for ev in ({}, None, {"pr:x": "deferred"}, {"pr:1": None}, {5: "deferred"},
                   {"issue:2": "deferred to follow-up patches"}):
            self.assertIsInstance(deferred_claims(ev), dict)


class ThePackageMarksTheDecision(unittest.TestCase):
    """RED before `rests_on_deferred` shipped: the decision came back with no
    signal at all that it described a past moment."""

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                        # pragma: no cover
            raise unittest.SkipTest("temporal fixture missing")
        cls.texts = _texts()

    def test_the_recorded_decision_is_flagged_and_names_the_successor(self):
        decision = _package(self.texts)["decisions"][0]
        self.assertTrue(decision.get("rests_on_deferred"))
        self.assertEqual(decision.get("later_merged"), [LATER])

    def test_the_decision_is_otherwise_untouched(self):
        """The flag ANNOTATES. It must not rewrite the answer, downgrade the
        support class, or drop the decision -- suppressing it would hide a claim
        that may well still be true."""
        decision = _package(self.texts)["decisions"][0]
        self.assertEqual(decision["text"], RECORDED_DECISION)
        self.assertEqual(decision["support"], "explicit")
        self.assertEqual(decision["citations"], [DEFERRING])

    def test_a_decision_citing_only_the_successor_is_NOT_flagged(self):
        decision = _package(self.texts, citations=(LATER,))["decisions"][0]
        self.assertNotIn("rests_on_deferred", decision)
        self.assertNotIn("later_merged", decision)

    def test_the_key_is_ABSENT_not_false_when_it_does_not_apply(self):
        """Same rule as `review` in attempts.py: a `false` on every decision is
        noise a reader learns to skip past, and this has to stay noticeable."""
        decision = _package(self.texts, citations=(LATER,))["decisions"][0]
        self.assertNotIn("rests_on_deferred", decision.keys())
