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


if __name__ == "__main__":
    unittest.main()
