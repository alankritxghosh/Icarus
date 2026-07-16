# evals/test_gate.py
"""The gate's conscience: an answer survives ONLY when grounded; everything
ambiguous collapses to honest abstention. These prove the model cannot make us
bluff."""

import json
import unittest

from .gate import gate

RETRIEVED = ["pr:1435", "issue:506", "code:llm/models.py"]


def _ans(answer, citations):
    return json.dumps({"verdict": "answer", "answer": answer, "citations": citations})


class GateTests(unittest.TestCase):
    def test_grounded_answer_passes(self):
        r = gate(_ans("Because Y.", ["pr:1435"]), RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])
        self.assertTrue(r.answer)

    def test_drops_citations_not_retrieved_but_keeps_grounded_ones(self):
        r = gate(_ans("Because Y.", ["pr:1435", "pr:9999"]), RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])  # pr:9999 dropped

    def test_answer_with_only_unretrieved_citations_forces_unknown(self):
        self.assertEqual(gate(_ans("Made up.", ["pr:9999"]), RETRIEVED).verdict, "unknown")

    def test_empty_citations_forces_unknown(self):
        self.assertEqual(gate(_ans("No source.", []), RETRIEVED).verdict, "unknown")

    def test_empty_answer_forces_unknown(self):
        self.assertEqual(gate(_ans("", ["pr:1435"]), RETRIEVED).verdict, "unknown")

    def test_explicit_unknown(self):
        self.assertEqual(gate(json.dumps({"verdict": "unknown"}), RETRIEVED).verdict, "unknown")

    def test_unparseable_text_forces_unknown(self):
        self.assertEqual(gate("the model rambled with no json", RETRIEVED).verdict, "unknown")

    def test_json_embedded_in_prose_is_extracted(self):
        raw = "Sure!\n" + _ans("Because Y.", ["pr:1435"]) + "\nhope that helps"
        self.assertEqual(gate(raw, RETRIEVED).verdict, "answer")

    def test_case_insensitive_verdict_still_answers(self):
        # A writer emitting "Answer"/"ANSWER" instead of lowercase "answer"
        # must not be wrongly forced to unknown -- fail-safe-only hardening,
        # can only ever turn a would-be-unknown into a legitimate answer.
        raw = json.dumps({"verdict": "Answer", "answer": "Because Y.", "citations": ["pr:1435"]})
        r = gate(raw, RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])

    def test_single_string_citation_still_grounds(self):
        # A writer emitting a lone citation string instead of a one-item list
        # must still ground, not be forced to unknown for a format mismatch.
        raw = json.dumps({"verdict": "answer", "answer": "Because Y.", "citations": "pr:1435"})
        r = gate(raw, RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])


class MalformedLineWindowTests(unittest.TestCase):
    """A citation whose line window is impossible (line 0/negative or end<start)
    is not a real location -- it can only be fabricated or garbled, so it must
    never ground (Sol P0). Well-formed contained windows still ground."""

    def test_inverted_range_forced_unknown(self):
        r = gate(_ans("x", ["code:f.py#L300-L250"]), ["code:f.py#L250-L300"])
        self.assertEqual(r.verdict, "unknown")

    def test_line_zero_forced_unknown(self):
        r = gate(_ans("x", ["code:f.py#L0"]), ["code:f.py"])
        self.assertEqual(r.verdict, "unknown")

    def test_wellformed_contained_window_still_grounds(self):
        r = gate(_ans("x", ["code:f.py#L260-L280"]), ["code:f.py#L250-L300"])
        self.assertEqual(r.verdict, "answer")


class RationaleGuardTests(unittest.TestCase):
    """(b) The gate refuses a rationale-seeking ("why") question whose grounded
    evidence states no actual reason -- catching the "answered the what, dodged
    the why" failure groundedness alone is blind to. Only active when the caller
    supplies question + evidence; fail-safe (only ever adds abstention)."""

    CODE_EVIDENCE = {"code:llm/models.py": "CONVERSATION_NAME_LENGTH = 32"}
    REASON_EVIDENCE = {"pr:1435": "We capped names at 32 so that they stay readable."}

    def test_why_over_code_with_no_reason_abstains(self):
        r = gate(_ans("It's 32, set in models.py", ["code:llm/models.py"]),
                 ["code:llm/models.py"],
                 question="Why is the limit 32 specifically?", evidence=self.CODE_EVIDENCE)
        self.assertEqual(r.verdict, "unknown")

    def test_why_with_recorded_reason_answers(self):
        r = gate(_ans("Because names stay readable.", ["pr:1435"]),
                 ["pr:1435"],
                 question="Why is the limit 32?", evidence=self.REASON_EVIDENCE)
        self.assertEqual(r.verdict, "answer")

    def test_why_with_discussion_source_answers_even_without_marker(self):
        # A pr/issue/doc citation IS recorded discussion -- it clears (b) even if
        # its snippet has no explicit marker word (real answerable why-questions
        # cite the PR/issue that discusses the change).
        ev = {"pr:1432": "Add an options= dict parameter to .prompt() and .reply()."}
        r = gate(_ans("It adds an options dict.", ["pr:1432"]), ["pr:1432"],
                 question="Why does .prompt() accept an options= dict?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_non_why_question_over_code_answers(self):
        r = gate(_ans("The limit is 32.", ["code:llm/models.py"]),
                 ["code:llm/models.py"],
                 question="What is the max name length?", evidence=self.CODE_EVIDENCE)
        self.assertEqual(r.verdict, "answer")

    def test_guard_inactive_without_question_or_evidence(self):
        # Back-compat: a 2-arg call (no question/evidence) keeps the old behavior.
        r = gate(_ans("It's 32.", ["code:llm/models.py"]), ["code:llm/models.py"])
        self.assertEqual(r.verdict, "answer")


if __name__ == "__main__":
    unittest.main()
