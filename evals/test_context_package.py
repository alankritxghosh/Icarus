"""`build_context_package` — the structured shape Experiment B's `icarus.
context(task)` returns. Pure reshaping, no writer, no I/O: constructs real
Investigation/Result/structure objects directly and asserts on the output.

Weighted toward what must NOT leak in: a WEAK finding (code alone) must not
read as a "decision", risks must include an attempt the answer never cited,
and "symbols" must never appear -- this schema deliberately drops it rather
than shipping a permanently-empty field.
"""
import unittest

from evals.context_package import build_context_package
from evals.investigation import Claim, EvidenceRef, Investigation
from evals.pipeline import Result

STRUCTURE = {
    "file_edges": [["a.py", "b.py"]],
    "file_edge_evidence": [{"source": "a.py", "target": "b.py", "ref": "code:a.py#L1-L5"}],
    "package_edges": [],
    "components": [{"directory": "llm", "depends_on": ["llm/utils"], "file_count": 3}],
    "most_depended_on_files": ["llm/utils.py"],
    "unresolved_import_count": 2,
    "unanalysed_languages": ["Rust"],
}

REJECTED_PR_TEXT = "PR #99: Add caching layer\n[CLOSED by someone]\nBody."


def _inv(objective="add OAuth callback handling", evidence=None, claims=None):
    inv = Investigation(objective=objective, question=objective)
    for ref, (source, states_reason) in (evidence or {}).items():
        inv.evidence[ref] = EvidenceRef(ref=ref, source=source, via="t1",
                                        states_reason=states_reason)
    inv.claims = claims or []
    return inv


class DecisionsTests(unittest.TestCase):

    def test_explicit_and_strong_claims_are_decisions(self):
        inv = _inv(claims=[
            Claim(id="c1", text="chosen for X", citations=["pr:1"],
                  support="explicit", verified=True),
            Claim(id="c2", text="corroborated two ways", citations=["pr:2", "code:a.py"],
                  support="strong", verified=True),
        ])
        result = Result(verdict="answer", citations=["pr:1"])
        out = build_context_package(inv, result, STRUCTURE, texts={})
        texts = {d["text"] for d in out["decisions"]}
        self.assertEqual(texts, {"chosen for X", "corroborated two ways"})

    def test_weak_claim_is_not_a_decision(self):
        """Code alone proves WHAT, never WHY -- see investigation.py's own
        SUPPORT_HEADLINES. A weak claim must not read as a decision."""
        inv = _inv(claims=[Claim(id="c1", text="the code does X",
                                 citations=["code:a.py"], support="weak", verified=True)])
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["decisions"], [])

    def test_unverified_claim_is_not_a_decision(self):
        inv = _inv(claims=[Claim(id="c1", text="x", citations=["pr:1"],
                                 support="explicit", verified=False)])
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["decisions"], [])


class RisksTests(unittest.TestCase):

    def test_a_gathered_but_uncited_rejected_pr_is_a_risk(self):
        """The whole point: a refused attempt is worth surfacing whether or not
        the conclusion happened to cite it (evals/attempts.py's own docstring)."""
        inv = _inv(evidence={"pr:99": ("pr", False)})
        result = Result(verdict="answer", citations=[])  # did NOT cite pr:99
        out = build_context_package(inv, result, STRUCTURE, texts={"pr:99": REJECTED_PR_TEXT})
        self.assertEqual([r["ref"] for r in out["risks"]], ["pr:99"])

    def test_no_risks_when_nothing_was_refused(self):
        inv = _inv(evidence={"pr:1": ("pr", True)})
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE,
                                    texts={"pr:1": "PR #1: X\n[MERGED by a]\nBody."})
        self.assertEqual(out["risks"], [])


class GroupingTests(unittest.TestCase):

    def test_prs_issues_files_split_by_source_and_deduped(self):
        inv = _inv(evidence={
            "pr:1": ("pr", False), "pr:2": ("pr", False),
            "issue:5": ("issue", False),
            "code:a.py#L1-L10": ("code", False), "code:a.py#L20-L30": ("code", False),
        })
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["prs"], ["pr:1", "pr:2"])
        self.assertEqual(out["issues"], ["issue:5"])
        self.assertEqual(out["files"], ["a.py"])  # deduped across two windows

    def test_commit_and_doc_sources_are_not_files_prs_or_issues(self):
        inv = _inv(evidence={"commit:abc": ("commit", False), "doc:README.md": ("doc", False)})
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["prs"], [])
        self.assertEqual(out["issues"], [])
        self.assertEqual(out["files"], [])

    def test_order_mirrors_evidence_absorption_order(self):
        inv = _inv(evidence={"pr:3": ("pr", False), "pr:1": ("pr", False)})
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["prs"], ["pr:3", "pr:1"])


class StructurePassthroughTests(unittest.TestCase):

    def test_architecture_and_dependencies_come_straight_from_structure(self):
        out = build_context_package(_inv(), Result(verdict="unknown"), STRUCTURE, texts={})
        self.assertEqual(out["architecture"], STRUCTURE["components"])
        self.assertEqual(out["dependencies"]["file_edges"], STRUCTURE["file_edges"])
        self.assertEqual(out["dependencies"]["package_edges"], STRUCTURE["package_edges"])

    def test_empty_structure_yields_empty_not_omitted(self):
        out = build_context_package(_inv(), Result(verdict="unknown"), {}, texts={})
        self.assertEqual(out["architecture"], [])
        self.assertEqual(out["dependencies"], {"file_edges": [], "package_edges": []})


class ConstraintsTests(unittest.TestCase):

    def test_budget_note_becomes_a_constraint(self):
        inv = _inv()
        inv.stopped_because = "reached the maximum number of investigation rounds"
        inv.budget.rounds_spent = inv.budget.max_rounds
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertIn(inv.budget.exhausted_reason(), out["constraints"])

    def test_no_budget_note_when_not_truncated(self):
        out = build_context_package(_inv(), Result(verdict="answer"), STRUCTURE, texts={})
        self.assertNotIn(None, out["constraints"])

    def test_unanalysed_languages_and_unresolved_imports_are_constraints(self):
        out = build_context_package(_inv(), Result(verdict="answer"), STRUCTURE, texts={})
        joined = " ".join(out["constraints"])
        self.assertIn("Rust", joined)
        self.assertIn("2", joined)


class TopLevelShapeTests(unittest.TestCase):

    def test_task_is_the_objective(self):
        out = build_context_package(_inv(objective="implement rate limiting"),
                                    Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["task"], "implement rate limiting")

    def test_unknowns_pass_through(self):
        inv = _inv()
        inv.unknowns = ["nobody recorded why the timeout is 30s"]
        out = build_context_package(inv, Result(verdict="answer"), STRUCTURE, texts={})
        self.assertEqual(out["unknowns"], inv.unknowns)

    def test_citations_come_from_the_result_not_from_everything_gathered(self):
        """citations is what the GATED answer actually rests on -- narrower than
        risks/prs/issues, which report everything the investigation touched."""
        inv = _inv(evidence={"pr:1": ("pr", False), "pr:2": ("pr", False)})
        result = Result(verdict="answer", citations=["pr:1"])
        out = build_context_package(inv, result, STRUCTURE, texts={})
        self.assertEqual(out["citations"], ["pr:1"])
        self.assertEqual(out["prs"], ["pr:1", "pr:2"])  # both gathered

    def test_no_symbols_key(self):
        """Deliberately dropped from the original brief's schema -- nothing
        extracts symbols cheaply and honestly today. A permanently-empty field
        would be worse than a documented omission."""
        out = build_context_package(_inv(), Result(verdict="answer"), STRUCTURE, texts={})
        self.assertNotIn("symbols", out)

    def test_every_documented_key_is_present_even_when_empty(self):
        out = build_context_package(_inv(), Result(verdict="unknown"), {}, texts={})
        for key in ("task", "architecture", "dependencies", "files", "decisions",
                   "prs", "issues", "risks", "constraints", "unknowns", "citations"):
            self.assertIn(key, out)


if __name__ == "__main__":
    unittest.main()
