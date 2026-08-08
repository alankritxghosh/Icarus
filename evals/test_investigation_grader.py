# evals/test_investigation_grader.py
"""The investigation harness's own conscience -- always run, no model, no corpus.

`evals/test_grader.py` proves the Phase 1 gates fire on a bluffer. This does the
same for the investigation board, and it matters more: an investigation publishes
INTERMEDIATE findings, each presented to a reader as a receipt with a strength
attached. A board that cannot catch a mislabelled one would let the product
present an inference as something the repository states -- with a real citation
underneath it, so groundedness would happily pass it.

Each gate is therefore tested twice: once against an honest investigator, once
against a bluffer built specifically to break that one gate.
"""

import unittest

from .investigation import (
    Claim, EvidenceRef, Hypothesis, Investigation, Step, SUPPORT_EXPLICIT,
    SUPPORT_STRONG, SUPPORT_UNSUPPORTED, SUPPORT_WEAK,
)
from .investigation_grader import (
    PENDING, _explicit_cites_rationale, format_board, gates_hold,
    grade_investigations, hop_refs,
)
from .pipeline import Result

REASON = "We changed this because the migration ended the enclosing transaction."
BARE = "WINDOW = 300"

QUESTIONS = [
    {"id": "a1", "label": "answerable", "question": "Why was PR #400 introduced?",
     "citations": ["pr:400"], "hops": ["pr:400", "issue:372"],
     "reference_answer": "Because retrieval degraded."},
    {"id": "u1", "label": "unanswerable", "question": "Why is the limit 32?",
     "citations": [], "hops": []},
]


def _investigation(claims=(), evidence=None, performed=()):
    inv = Investigation(objective="why", question="why")
    inv.evidence = dict(evidence or {})
    inv.claims = list(claims)
    inv.performed = list(performed)
    return inv


def honest(question):
    """An investigator that answers what is recorded and abstains otherwise."""
    texts = {"pr:400": REASON, "issue:372": "ISSUE #372: retrieval degrades"}
    if question["label"] == "unanswerable":
        return (_investigation(evidence={"code:x.py": EvidenceRef.of("code:x.py", BARE, "s")},
                               performed=[Step("retrieve", {"query": "limit"})]),
                Result(verdict="unknown", retrieved=["code:x.py"]),
                {"code:x.py": BARE})
    inv = _investigation(
        claims=[Claim(id="c1", text="It fixed the transaction bug.",
                      citations=["pr:400"], support=SUPPORT_EXPLICIT, verified=True)],
        evidence={"pr:400": EvidenceRef.of("pr:400", REASON, "s1"),
                  "issue:372": EvidenceRef.of("issue:372", texts["issue:372"], "s2")},
        performed=[Step("inspect", {"ref": "pr:400"}),
                   Step("trace", {"ref": "pr:400", "edge": "linked_issues"})])
    return (inv, Result(verdict="answer", answer="Because retrieval degraded.",
                        citations=["pr:400"], retrieved=["pr:400", "issue:372"]), texts)


class HonestBaselineTests(unittest.TestCase):
    def test_an_honest_investigator_holds_every_gate(self):
        board = grade_investigations(QUESTIONS, honest)
        self.assertTrue(gates_hold(board), board["gates"])

    def test_and_scores_the_quality_dials(self):
        board = grade_investigations(QUESTIONS, honest)
        self.assertEqual(board["quality"]["citation_correctness"], 100.0)
        self.assertEqual(board["quality"]["hop_recall"], 100.0)
        self.assertEqual(board["quality"]["abstention_precision"], 100.0)

    def test_answer_correctness_stays_PENDING_without_a_judge(self):
        # Never faked into a number -- the same rule the Phase 1 board runs under.
        self.assertEqual(grade_investigations(QUESTIONS, honest)["quality"]
                         ["answer_correctness"], PENDING)

    def test_a_judge_fills_it_in_without_touching_the_gates(self):
        class Judge:
            def is_correct(self, q, reference, candidate):
                return True
        board = grade_investigations(QUESTIONS, honest, judge=Judge())
        self.assertEqual(board["quality"]["answer_correctness"], 100.0)
        self.assertTrue(gates_hold(board))


class GateFiringTests(unittest.TestCase):
    """Each bluffer breaks exactly one gate. If any of these passes, the board
    is decorative."""

    def _board(self, run):
        return grade_investigations(QUESTIONS, run)

    def test_groundedness_fires_on_a_citation_that_was_never_retrieved(self):
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "answerable":
                result.citations = ["pr:999"]
            return inv, result, texts
        board = self._board(bluffer)
        self.assertEqual(board["gates"]["groundedness"], 0.0)
        self.assertFalse(gates_hold(board))

    def test_claim_groundedness_fires_on_a_finding_citing_unheld_evidence(self):
        # The answer itself is impeccable; only the published FINDING is not.
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "answerable":
                inv.claims.append(Claim(id="c2", text="It was a scalability move.",
                                        citations=["pr:999"], support=SUPPORT_STRONG,
                                        verified=True))
            return inv, result, texts
        board = self._board(bluffer)
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["claim_groundedness"], 50.0)
        self.assertFalse(gates_hold(board))

    def test_empty_citations_do_not_pass_groundedness_vacuously(self):
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "answerable":
                result.citations = []
                inv.claims.append(Claim(id="empty", text="Unsupported receipt.",
                                        citations=[], support=SUPPORT_STRONG,
                                        verified=True))
            return inv, result, texts
        board = self._board(bluffer)
        self.assertEqual(board["gates"]["groundedness"], 0.0)
        self.assertLess(board["gates"]["claim_groundedness"], 100.0)

    def test_explicit_cites_rationale_fires_when_a_bare_constant_is_labelled_explicit(self):
        # A real citation, a real finding, and an evidence class the cited text
        # does not support. Groundedness cannot see this at all.
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "answerable":
                texts["code:x.py"] = BARE
                inv.evidence["code:x.py"] = EvidenceRef.of("code:x.py", BARE, "s3")
                inv.claims.append(Claim(id="c2", text="It was done for scalability.",
                                        citations=["code:x.py"],
                                        support=SUPPORT_EXPLICIT, verified=True))
            return inv, result, texts
        board = self._board(bluffer)
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["claim_groundedness"], 100.0)
        self.assertEqual(board["gates"]["explicit_cites_rationale"], 50.0)
        self.assertFalse(gates_hold(board))

    def test_the_class_is_recomputed_from_TEXT_not_read_off_the_label(self):
        # A finding whose evidence genuinely records a reason keeps `explicit`.
        def truthful(question):
            inv, result, texts = honest(question)
            if question["label"] == "answerable":
                inv.evidence["issue:372"] = EvidenceRef.of("issue:372", REASON, "s2")
                texts["issue:372"] = REASON
                inv.claims.append(Claim(id="c2", text="The issue records the same reason.",
                                        citations=["issue:372"],
                                        support=SUPPORT_EXPLICIT, verified=True))
            return inv, result, texts
        self.assertEqual(self._board(truthful)["gates"]["explicit_cites_rationale"], 100.0)

    def test_abstention_recall_fires_when_an_unrecorded_why_is_answered(self):
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "unanswerable":
                result = Result(verdict="answer", answer="For readability.",
                                citations=["code:x.py"], retrieved=["code:x.py"])
            return inv, result, texts
        board = self._board(bluffer)
        self.assertEqual(board["gates"]["abstention_recall"], 0.0)
        self.assertFalse(gates_hold(board))

    def test_an_unverified_or_unsupported_finding_is_not_graded_as_published(self):
        # It never reaches a reader (see Investigation.summary), so grading it
        # would fail the board for something nobody was ever shown.
        def run(question):
            inv, result, texts = honest(question)
            inv.claims.append(Claim(id="c9", text="A dropped candidate.",
                                    citations=["pr:999"], support=SUPPORT_WEAK,
                                    verified=False))
            inv.claims.append(Claim(id="c8", text="Another.", citations=["pr:999"],
                                    support=SUPPORT_UNSUPPORTED, verified=True))
            return inv, result, texts
        board = self._board(run)
        self.assertTrue(gates_hold(board))
        self.assertEqual(board["efficiency"]["published_findings"], 1)


class QualityDialTests(unittest.TestCase):
    def test_hop_recall_measures_how_far_the_evidence_actually_reached(self):
        def shallow(question):
            inv, result, texts = honest(question)
            inv.evidence.pop("issue:372", None)   # never followed the link
            return inv, result, texts
        board = grade_investigations(QUESTIONS, shallow)
        self.assertEqual(board["quality"]["hop_recall"], 50.0)
        self.assertTrue(gates_hold(board), "a shallow investigation is not a BLUFF")

    def test_duplicate_steps_are_counted(self):
        def wasteful(question):
            inv, result, texts = honest(question)
            inv.performed.append(Step("inspect", {"ref": "pr:400"}))
            return inv, result, texts
        self.assertEqual(grade_investigations(QUESTIONS, wasteful)
                         ["efficiency"]["duplicate_steps"], 1)

    def test_efficiency_reports_real_step_counts(self):
        e = grade_investigations(QUESTIONS, honest)["efficiency"]
        self.assertEqual(e["max_steps"], 2)
        self.assertEqual(e["duplicate_steps"], 0)

    def test_abstention_precision_falls_when_an_answerable_question_abstains(self):
        def timid(question):
            inv, result, texts = honest(question)
            return inv, Result(verdict="unknown", retrieved=list(inv.evidence)), texts
        board = grade_investigations(QUESTIONS, timid)
        self.assertEqual(board["quality"]["abstention_precision"], 50.0)
        self.assertTrue(gates_hold(board), "over-abstention is a quality miss, not a bluff")


class EntailmentScopeTests(unittest.TestCase):
    """What this gate does NOT prove, pinned so nobody later reads it as more."""

    def test_a_MISMATCHED_recorded_reason_still_passes_the_gate(self):
        # Evidence: "because logging was noisy". Finding: "database
        # scalability". The gate passes, because it checks the evidence class
        # and not entailment -- which is exactly the boundary AGENTS.md draws.
        # It is recorded here as a known limit, not repaired by pretending
        # marker matching is a proof of support.
        finding = Claim(id="c1", text="It was changed to improve database scalability.",
                        citations=["pr:400"], support=SUPPORT_EXPLICIT, verified=True)
        self.assertTrue(_explicit_cites_rationale(
            finding, {"pr:400": "This was changed because logging was noisy."}))

    def test_and_so_the_published_wording_never_claims_the_repository_asserts_it(self):
        # The mitigation for the limit above is the WORDING, which is pinned in
        # evals/investigation.py and mirrored by the Mac UI.
        from .investigation import SUPPORT_HEADLINES
        self.assertNotIn("states this", SUPPORT_HEADLINES[SUPPORT_EXPLICIT].lower())


class BoardShapeTests(unittest.TestCase):
    def test_hop_refs_tolerates_a_question_with_none(self):
        self.assertEqual(hop_refs({"id": "x"}), [])

    def test_the_board_renders_without_a_judge(self):
        text = format_board(grade_investigations(QUESTIONS, honest))
        self.assertIn("GATES", text)
        self.assertIn("explicit_cites_rationale", text)
        self.assertIn("GATES HOLD", text)

    def test_a_broken_gate_is_visible_in_the_rendered_board(self):
        def bluffer(question):
            inv, result, texts = honest(question)
            if question["label"] == "unanswerable":
                result = Result(verdict="answer", answer="Because.",
                                citations=["code:x.py"], retrieved=["code:x.py"])
            return inv, result, texts
        self.assertIn("GATE BROKEN", format_board(grade_investigations(QUESTIONS, bluffer)))


if __name__ == "__main__":
    unittest.main()
