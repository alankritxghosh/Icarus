# evals/test_investigation.py
"""Investigation state's contract.

The load-bearing tests here are the ones that keep a MODEL out of decisions the
product cannot let a model make: how strongly evidence supports a claim, whether
a hypothesis holds, and when to stop. Each of those is pinned against the real
honesty gate rather than a hand-copied rule, so the two can never drift apart.
"""

import unittest

from . import gate as gate_mod
from .investigation import (
    HYPOTHESIS_OPEN, HYPOTHESIS_PARTIAL, HYPOTHESIS_REFUTED, HYPOTHESIS_SUPPORTED,
    HYPOTHESIS_UNSUPPORTED, STOP_BUDGET, STOP_DECIDED, STOP_DIMINISHING,
    STOP_EXHAUSTED, SUPPORT_EXPLICIT, SUPPORT_STRONG, SUPPORT_UNSUPPORTED,
    SUPPORT_WEAK, SUPPORT_HEADLINES, SUPPORT_ORDER, Budget, Claim, EvidenceRef,
    Hypothesis, Investigation, Step, _RATIONALE_SOURCES, classify_support,
    score_hypothesis,
)

REASON_TEXT = "We chose 300 lines because larger windows broke retrieval."
BARE_CODE = "WINDOW = 300"


def ev(ref, text=BARE_CODE, via="s1"):
    return EvidenceRef.of(ref, text, via)


def claim(cid, cites, hid=None, polarity=True, verified=True, support=SUPPORT_STRONG):
    return Claim(id=cid, text=f"claim {cid}", citations=list(cites), support=support,
                 hypothesis_id=hid, polarity=polarity, verified=verified)


class SupportClassificationTests(unittest.TestCase):
    def test_prose_that_records_a_reason_is_explicit(self):
        e = {"pr:400": ev("pr:400", REASON_TEXT)}
        self.assertEqual(classify_support(["pr:400"], e), SUPPORT_EXPLICIT)

    def test_two_independent_kinds_of_evidence_are_strong(self):
        e = {"pr:400": ev("pr:400"), "code:a.py": ev("code:a.py")}
        self.assertEqual(classify_support(["pr:400", "code:a.py"], e), SUPPORT_STRONG)

    def test_one_source_cited_twice_is_not_strong(self):
        # A pull request agreeing with itself is one account, not corroboration.
        e = {"pr:400": ev("pr:400"), "pr:401": ev("pr:401")}
        self.assertEqual(classify_support(["pr:400", "pr:401"], e), SUPPORT_WEAK)

    def test_code_alone_is_weak_however_much_of_it(self):
        # Code proves what happens. It never records why it was chosen.
        e = {f"code:{i}.py": ev(f"code:{i}.py") for i in range(5)}
        self.assertEqual(classify_support(list(e), e), SUPPORT_WEAK)

    def test_no_evidence_is_unsupported(self):
        self.assertEqual(classify_support([], {}), SUPPORT_UNSUPPORTED)

    def test_a_citation_to_evidence_never_retrieved_is_ignored_not_counted(self):
        # A model naming an unheld ref may only ever LOWER the class.
        e = {"pr:400": ev("pr:400", REASON_TEXT)}
        self.assertEqual(classify_support(["pr:400", "pr:999"], e), SUPPORT_EXPLICIT)
        self.assertEqual(classify_support(["pr:999"], e), SUPPORT_UNSUPPORTED)

    def test_duplicate_citations_do_not_manufacture_corroboration(self):
        e = {"pr:400": ev("pr:400")}
        self.assertEqual(classify_support(["pr:400", "pr:400"], e), SUPPORT_WEAK)

    def test_rationale_prose_in_a_CODE_chunk_is_not_explicit(self):
        # Only sources that carry a written explanation may reach EXPLICIT --
        # the same restriction the gate's (b) guard applies.
        e = {"code:a.py": ev("code:a.py", REASON_TEXT)}
        self.assertEqual(classify_support(["code:a.py"], e), SUPPORT_WEAK)


class EntailmentOverclaimTests(unittest.TestCase):
    """The conscience test for what `explicit` may be presented as.

    AGENTS.md draws the boundary precisely: groundedness is deterministic, while
    arbitrary semantic entailment is writer-reliant and CANNOT be proven in code
    without another model. Marker matching proves that a cited chunk records SOME
    reason. It cannot prove that reason is the reason for THIS finding.

    So the label is a statement about the EVIDENCE, and no wording anywhere may
    upgrade it into a statement that the repository asserts the finding.
    """

    MISMATCHED = "This was changed because logging was noisy."
    FINDING = "It was changed to improve database scalability."

    def test_marker_matching_cannot_tell_a_matched_reason_from_a_mismatched_one(self):
        # Both reach the same class. That is the honest limit of the mechanism,
        # stated here so nobody later mistakes the class for entailment.
        matched = {"pr:1": ev("pr:1", "Changed because retrieval degraded.")}
        mismatched = {"pr:1": ev("pr:1", self.MISMATCHED)}
        self.assertEqual(classify_support(["pr:1"], matched),
                         classify_support(["pr:1"], mismatched))

    def test_no_support_headline_claims_the_repository_ASSERTS_the_finding(self):
        # The wording is the whole exposure: "The repository states this" over a
        # finding the repository does not state is a bluff that groundedness
        # cannot catch, because the citation underneath it is real.
        banned = ("states this", "proves", "confirms", "guarantees",
                  "establishes this", "verified by the repository")
        for support, headline in SUPPORT_HEADLINES.items():
            low = headline.lower()
            for phrase in banned:
                self.assertNotIn(phrase, low, f"{support}: {headline!r}")

    def test_the_explicit_headline_describes_the_EVIDENCE_not_the_entailment(self):
        headline = SUPPORT_HEADLINES[SUPPORT_EXPLICIT].lower()
        self.assertIn("cite", headline)
        self.assertIn("reason", headline)

    def test_every_support_class_has_a_headline(self):
        for support in SUPPORT_ORDER:
            self.assertIn(support, SUPPORT_HEADLINES)


class GateAlignmentTests(unittest.TestCase):
    """The classifier must speak the gate's language, not a copy of it."""

    def test_rationale_sources_match_the_gates_own_list(self):
        # gate._records_reason is a closure inside gate(); its list is written
        # inline there. If that list changes, this must be updated deliberately
        # rather than drifting -- so pin the exact tuple.
        self.assertEqual(_RATIONALE_SOURCES, ("pr", "issue", "doc", "commit"))

    def test_states_reason_is_the_gates_function_not_a_reimplementation(self):
        self.assertTrue(ev("pr:1", REASON_TEXT).states_reason)
        self.assertFalse(ev("pr:1", BARE_CODE).states_reason)
        # ...and it agrees with the gate on the same text, by construction.
        self.assertEqual(ev("pr:1", REASON_TEXT).states_reason,
                         gate_mod._states_reason(REASON_TEXT))

    def test_source_is_read_by_the_gates_parser(self):
        self.assertEqual(ev("code:llm/cli.py#L1-L300").source, "code")
        self.assertEqual(ev("not-a-known-source:x").source, "unknown")


class HypothesisScoringTests(unittest.TestCase):
    def test_strong_support_with_nothing_against_is_supported(self):
        h = Hypothesis("h1", "it was a scalability change", supporting=["c1"])
        self.assertEqual(score_hypothesis(h, {"c1": claim("c1", ["pr:400"], "h1")}),
                         HYPOTHESIS_SUPPORTED)

    def test_only_weak_support_stays_partial(self):
        h = Hypothesis("h1", "x", supporting=["c1"])
        c = claim("c1", ["code:a.py"], "h1", support=SUPPORT_WEAK)
        self.assertEqual(score_hypothesis(h, {"c1": c}), HYPOTHESIS_PARTIAL)

    def test_evidence_both_ways_is_partial_not_silently_resolved(self):
        # Deciding a contradiction quietly is how a confident wrong answer is
        # made. It must survive to the reader.
        h = Hypothesis("h1", "x", supporting=["c1"], contradicting=["c2"])
        claims = {"c1": claim("c1", ["pr:400"], "h1"),
                  "c2": claim("c2", ["pr:412"], "h1", polarity=False)}
        self.assertEqual(score_hypothesis(h, claims), HYPOTHESIS_PARTIAL)

    def test_only_contradicting_evidence_refutes(self):
        h = Hypothesis("h1", "x", contradicting=["c2"])
        c = claim("c2", ["pr:412"], "h1", polarity=False)
        self.assertEqual(score_hypothesis(h, {"c2": c}), HYPOTHESIS_REFUTED)

    def test_no_evidence_is_unsupported_never_supported_by_default(self):
        self.assertEqual(score_hypothesis(Hypothesis("h1", "x"), {}),
                         HYPOTHESIS_UNSUPPORTED)

    def test_an_UNVERIFIED_claim_cannot_support_a_hypothesis(self):
        h = Hypothesis("h1", "x", supporting=["c1"])
        c = claim("c1", ["pr:400"], "h1", verified=False)
        self.assertEqual(score_hypothesis(h, {"c1": c}), HYPOTHESIS_UNSUPPORTED)

    def test_an_unsupported_claim_cannot_support_a_hypothesis(self):
        h = Hypothesis("h1", "x", supporting=["c1"])
        c = claim("c1", [], "h1", support=SUPPORT_UNSUPPORTED)
        self.assertEqual(score_hypothesis(h, {"c1": c}), HYPOTHESIS_UNSUPPORTED)


class StepAndDedupeTests(unittest.TestCase):
    def test_step_id_is_the_call_itself(self):
        a = Step("inspect", {"ref": "pr:400"}, reason="x")
        b = Step("inspect", {"ref": "pr:400"}, reason="a different reason")
        self.assertEqual(a.id, b.id)          # same call, whatever the excuse
        self.assertNotEqual(a.id, Step("inspect", {"ref": "pr:401"}).id)

    def test_argument_order_does_not_change_identity(self):
        self.assertEqual(Step("trace", {"ref": "pr:400", "edge": "commits"}).id,
                         Step("trace", {"edge": "commits", "ref": "pr:400"}).id)

    def test_a_queued_or_performed_step_is_never_queued_again(self):
        inv = Investigation(objective="why")
        s = Step("inspect", {"ref": "pr:400"})
        self.assertTrue(inv.queue(s))
        self.assertFalse(inv.queue(Step("inspect", {"ref": "pr:400"})))
        inv.performed.append(inv.pending.pop())
        self.assertFalse(inv.queue(s))

    def test_take_round_is_bounded_by_parallelism_and_by_remaining_steps(self):
        inv = Investigation(objective="why", budget=Budget(max_parallel=2, max_steps=3))
        for i in range(5):
            inv.queue(Step("retrieve", {"query": str(i)}))
        self.assertEqual(len(inv.take_round()), 2)
        inv.budget.steps_spent = 3
        self.assertEqual(inv.take_round(), [])


class BudgetTests(unittest.TestCase):
    def test_each_ceiling_stops_a_round_and_names_itself(self):
        for spent, cap, note in (("rounds_spent", "max_rounds", "rounds"),
                                 ("steps_spent", "max_steps", "steps"),
                                 ("writer_calls_spent", "max_writer_calls", "reasoning calls"),
                                 ("evidence_chars_spent", "max_evidence_chars", "evidence")):
            b = Budget()
            setattr(b, spent, getattr(b, cap))
            self.assertFalse(b.allows_round(), spent)
            self.assertIn(note, b.exhausted_reason(), spent)

    def test_a_fresh_budget_allows_work_and_reports_no_ceiling(self):
        b = Budget()
        self.assertTrue(b.allows_round())
        self.assertIsNone(b.exhausted_reason())

    def test_spending_is_monotonic_and_chars_never_go_negative(self):
        b = Budget()
        b.spend_step(chars=-50)
        self.assertEqual((b.steps_spent, b.evidence_chars_spent), (1, 0))


class StoppingTests(unittest.TestCase):
    def _open(self):
        inv = Investigation(objective="why")
        inv.hypotheses = [Hypothesis("h1", "x")]
        inv.queue(Step("retrieve", {"query": "x"}))
        return inv

    def test_keeps_going_while_a_hypothesis_is_open_and_work_remains(self):
        self.assertIsNone(self._open().should_stop())

    def test_stops_when_nothing_is_left_to_investigate(self):
        inv = self._open()
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_EXHAUSTED)

    def test_decided_hypotheses_do_NOT_stop_a_run_with_work_still_queued(self):
        # Measured live: an investigation of PR #1525 traced its linked issue,
        # its changed file and its follow-up pull requests, then stopped before
        # READING any of them, because the PR body alone had already made its
        # hypothesis look supported. It scored 25% hop recall while reporting
        # itself finished. A hypothesis supported by one source that has not met
        # the evidence which could refute it is a hypothesis nobody has tested.
        inv = self._open()
        inv.hypotheses[0].status = HYPOTHESIS_SUPPORTED
        self.assertIsNone(inv.should_stop())

    def test_stops_as_DECIDED_once_the_queue_empties_with_all_settled(self):
        inv = self._open()
        inv.hypotheses[0].status = HYPOTHESIS_SUPPORTED
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_DECIDED)

    def test_an_empty_queue_with_something_unsettled_is_EXHAUSTED_not_decided(self):
        # Two different things to tell a reader: "I settled it" versus "I ran
        # out of moves".
        inv = self._open()
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_EXHAUSTED)

    def test_a_hypothesis_nothing_was_gathered_for_is_NOT_decided(self):
        # Found live on the committed corpus: a run ended after ONE round
        # reporting "every hypothesis decided" while a second hypothesis had
        # zero evidence and two queued steps that had never run. UNSUPPORTED
        # says how far the investigation got, not what the repository holds.
        inv = self._open()
        inv.hypotheses.append(Hypothesis("h2", "the untested one"))
        inv.hypotheses[0].status = HYPOTHESIS_SUPPORTED
        inv.hypotheses[1].status = HYPOTHESIS_UNSUPPORTED
        self.assertIsNone(inv.should_stop())
        # ...and once there is genuinely nothing left to try, it says THAT --
        # EXHAUSTED rather than DECIDED, because one hypothesis never was.
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_EXHAUSTED)

    def test_a_refuted_hypothesis_IS_decided(self):
        inv = self._open()
        inv.hypotheses[0].status = HYPOTHESIS_REFUTED
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_DECIDED)

    def test_an_open_contradiction_is_never_reported_as_decided(self):
        inv = self._open()
        inv.hypotheses[0].status = HYPOTHESIS_SUPPORTED
        inv.contradictions = [("c1", "c2", "x")]
        self.assertIsNone(inv.should_stop())
        inv.pending.clear()
        self.assertEqual(inv.should_stop(), STOP_EXHAUSTED)

    def test_two_rounds_that_find_no_new_evidence_end_it(self):
        inv = self._open()
        inv.note_round(new_refs=0)
        self.assertIsNone(inv.should_stop())     # one barren round is not enough
        inv.note_round(new_refs=0)
        self.assertEqual(inv.should_stop(), STOP_DIMINISHING)

    def test_a_productive_round_resets_the_diminishing_returns_counter(self):
        inv = self._open()
        inv.note_round(new_refs=0)
        inv.note_round(new_refs=3)
        inv.note_round(new_refs=0)
        self.assertIsNone(inv.should_stop())

    def test_budget_exhaustion_outranks_looking_finished(self):
        # A truncated investigation must never be reported as a complete one.
        inv = self._open()
        inv.hypotheses[0].status = HYPOTHESIS_SUPPORTED
        inv.budget.steps_spent = inv.budget.max_steps
        self.assertEqual(inv.should_stop(), STOP_BUDGET)
        self.assertIsNotNone(inv.budget.exhausted_reason())

    def test_a_run_with_no_hypotheses_does_not_claim_everything_is_decided(self):
        inv = Investigation(objective="why")
        inv.queue(Step("retrieve", {"query": "x"}))
        self.assertIsNone(inv.should_stop())


class StateIntegrationTests(unittest.TestCase):
    def test_absorb_counts_only_genuinely_new_refs(self):
        inv = Investigation(objective="why")
        self.assertEqual(inv.absorb({"pr:400": ev("pr:400")}), 1)
        self.assertEqual(inv.absorb({"pr:400": ev("pr:400"), "issue:1": ev("issue:1")}), 1)

    def test_add_claim_classifies_support_itself_and_ignores_what_it_was_given(self):
        inv = Investigation(objective="why")
        inv.absorb({"pr:400": ev("pr:400", REASON_TEXT)})
        c = inv.add_claim(Claim(id="c1", text="t", citations=["pr:400"],
                                support=SUPPORT_UNSUPPORTED))
        self.assertEqual(c.support, SUPPORT_EXPLICIT)

    def test_a_claim_attaches_to_its_hypothesis_on_the_right_side(self):
        inv = Investigation(objective="why", hypotheses=[Hypothesis("h1", "x")])
        inv.absorb({"pr:400": ev("pr:400"), "code:a.py": ev("code:a.py")})
        inv.add_claim(Claim(id="c1", text="for", citations=["pr:400"], hypothesis_id="h1"))
        inv.add_claim(Claim(id="c2", text="against", citations=["code:a.py"],
                            hypothesis_id="h1", polarity=False))
        self.assertEqual(inv.hypotheses[0].supporting, ["c1"])
        self.assertEqual(inv.hypotheses[0].contradicting, ["c2"])

    def test_contradictions_are_detected_only_between_VERIFIED_claims(self):
        inv = Investigation(objective="why", hypotheses=[Hypothesis("h1", "x")])
        inv.absorb({"pr:400": ev("pr:400"), "pr:412": ev("pr:412")})
        inv.add_claim(Claim(id="c1", text="for", citations=["pr:400"],
                            hypothesis_id="h1", verified=True))
        inv.add_claim(Claim(id="c2", text="against", citations=["pr:412"],
                            hypothesis_id="h1", polarity=False, verified=False))
        self.assertEqual(inv.detect_contradictions(), [])
        inv.claims[-1].verified = True
        self.assertEqual(len(inv.detect_contradictions()), 1)

    def test_summary_publishes_only_verified_claims_and_the_full_trail(self):
        inv = Investigation(objective="why was it introduced", subject=["pr:400"])
        inv.absorb({"pr:400": ev("pr:400", REASON_TEXT)})
        inv.add_claim(Claim(id="c1", text="shown", citations=["pr:400"], verified=True))
        inv.add_claim(Claim(id="c2", text="hidden", citations=["pr:400"], verified=False))
        inv.performed.append(Step("inspect", {"ref": "pr:400"}, reason="the subject"))
        out = inv.summary()
        self.assertEqual([c["text"] for c in out["claims"]], ["shown"])
        self.assertEqual(out["claims"][0]["support"], SUPPORT_EXPLICIT)
        self.assertEqual(len(out["trail"]), 1)

    def test_rescore_moves_a_hypothesis_off_open_once_claims_land(self):
        inv = Investigation(objective="why", hypotheses=[Hypothesis("h1", "x")])
        self.assertEqual(inv.hypotheses[0].status, HYPOTHESIS_OPEN)
        inv.absorb({"pr:400": ev("pr:400", REASON_TEXT)})
        inv.add_claim(Claim(id="c1", text="t", citations=["pr:400"],
                            hypothesis_id="h1", verified=True))
        inv.rescore()
        self.assertEqual(inv.hypotheses[0].status, HYPOTHESIS_SUPPORTED)


if __name__ == "__main__":
    unittest.main()
