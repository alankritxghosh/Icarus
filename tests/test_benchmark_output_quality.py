"""
Output-quality evaluator tests for the benchmark runner.

These exercise the new ``expected.*`` assertions added on top of the existing
classification / must_not_be_unknown / likely_evidence checks:

  - ``confidence``          — the emitted confidence level must match.
  - ``min_keyword_hits``    — N expected keywords must appear in cited excerpts.
  - ``forbidden_evidence``  — the answer must not rest solely on a forbidden path
                              (e.g. README-only citations).
  - ``max_confidence``      — no rationale finding may exceed a confidence ceiling
                              (guards the "generic prose -> false documented
                              decision" honesty risk).

Each check is a pure function of (report, expected), so these feed synthetic
reports directly to ``_evaluate_success`` rather than running real checkouts.
The reports mirror the shape ``report_to_dict`` emits.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.benchmark import _evaluate_success


def _eval(report, expected):
    """Call the evaluator the way the runner does: expected nested under a question."""
    return _evaluate_success(report, {"expected": expected})


def _finding(classification: str, confidence: str, statement: str, citations=()):
    return {
        "id": f"{classification[0]}001",
        "classification": classification,
        "confidence": confidence,
        "statement": statement,
        "citations": list(citations),
    }


def _evidence(item_id: str, path: str, excerpt: str = ""):
    return {"id": item_id, "path": path, "excerpt": excerpt}


def _report(*, observed=(), inferred=(), unknown=(), evidence=()):
    return {
        "findings": {
            "observed": list(observed),
            "inferred": list(inferred),
            "unknown": list(unknown),
        },
        "evidence": list(evidence),
        "warnings": [],
    }


class ConfidenceAssertionTests(unittest.TestCase):
    def test_passes_when_expected_confidence_present(self) -> None:
        report = _report(observed=[_finding("observed", "high", "decision recorded")])
        passed, reason, _ = _eval(
            report, {"classification": "observed", "confidence": "high"}
        )
        self.assertTrue(passed, reason)

    def test_fails_when_expected_confidence_absent(self) -> None:
        report = _report(observed=[_finding("observed", "high", "decision recorded")])
        passed, reason, _ = _eval(
            report, {"classification": "observed", "confidence": "medium"}
        )
        self.assertFalse(passed)
        self.assertIn("medium-confidence", reason)


class KeywordHitTests(unittest.TestCase):
    def test_passes_when_enough_keywords_in_cited_excerpts(self) -> None:
        report = _report(
            observed=[_finding("observed", "high", "decision", citations=["e1"])],
            evidence=[_evidence("e1", "docs/adr.md", "We chose an in-process queue because brokers add ops burden.")],
        )
        expected = {
            "keywords": ["in-process queue", "because", "kafka"],
            "min_keyword_hits": 2,
        }
        passed, reason, _ = _eval(
            report, expected)
        self.assertTrue(passed, reason)

    def test_fails_when_keywords_missing_from_excerpts(self) -> None:
        report = _report(
            observed=[_finding("observed", "high", "decision", citations=["e1"])],
            evidence=[_evidence("e1", "docs/adr.md", "Some unrelated prose with no topical terms.")],
        )
        expected = {"keywords": ["kafka", "rabbitmq"], "min_keyword_hits": 1}
        passed, reason, _ = _eval(
            report, expected)
        self.assertFalse(passed)
        self.assertIn("keywords", reason)

    def test_only_counts_excerpts_that_are_actually_cited(self) -> None:
        # The keyword lives in an evidence item no finding cites -> not counted.
        report = _report(
            observed=[_finding("observed", "high", "decision", citations=["e1"])],
            evidence=[
                _evidence("e1", "docs/adr.md", "nothing topical here"),
                _evidence("e2", "docs/other.md", "kafka kafka kafka"),
            ],
        )
        expected = {"keywords": ["kafka"], "min_keyword_hits": 1}
        passed, _, _ = _eval(
            report, expected)
        self.assertFalse(passed)


class ForbiddenEvidenceTests(unittest.TestCase):
    def test_fails_when_only_forbidden_path_is_cited(self) -> None:
        report = _report(
            observed=[_finding("observed", "high", "decision", citations=["e1"])],
            evidence=[_evidence("e1", "README.md", "some readme text")],
        )
        passed, reason, _ = _eval(
            report, {"forbidden_evidence": ["README.md"]})
        self.assertFalse(passed)
        self.assertIn("forbidden", reason)

    def test_passes_when_corroborating_path_also_cited(self) -> None:
        report = _report(
            observed=[_finding("observed", "high", "decision", citations=["e1", "e2"])],
            evidence=[
                _evidence("e1", "README.md", "readme"),
                _evidence("e2", "docs/adr.md", "adr"),
            ],
        )
        passed, reason, _ = _eval(
            report, {"forbidden_evidence": ["README.md"]})
        self.assertTrue(passed, reason)

    def test_passes_when_no_citations_at_all(self) -> None:
        # Honest-unknown answers may cite nothing; forbidden check must not fire.
        report = _report(unknown=[_finding("unknown", "low", "rationale is unknown")])
        passed, reason, _ = _eval(
            report, {"forbidden_evidence": ["README.md"]})
        self.assertTrue(passed, reason)


class MaxConfidenceTests(unittest.TestCase):
    def test_passes_when_rationale_finding_is_low(self) -> None:
        report = _report(
            observed=[_finding("observed", "high", "Git resolved HEAD to immutable commit abc.")],
            unknown=[_finding("unknown", "low", "The rationale requested is unknown.")],
        )
        passed, reason, _ = _eval(
            report, {"must_report_unknown_rationale": True, "max_confidence": "low"}
        )
        self.assertTrue(passed, reason)

    def test_fails_when_a_rationale_finding_is_high(self) -> None:
        # The §7 P1 shape: generic prose flips into a high-confidence documented rationale.
        report = _report(
            observed=[
                _finding("observed", "high", "Git resolved HEAD to immutable commit abc."),
                _finding("observed", "high", "Relevant text explicitly records a decision and nearby rationale."),
            ],
        )
        passed, reason, _ = _eval(
            report, {"max_confidence": "low"})
        self.assertFalse(passed)
        self.assertIn("max_confidence", reason)

    def test_ignores_non_rationale_infrastructure_findings(self) -> None:
        # observed/high HEAD + collection findings must NOT trip the ceiling.
        report = _report(
            observed=[
                _finding("observed", "high", "Git resolved HEAD to immutable commit abc."),
                _finding("observed", "high", "Collected 12 bounded doc evidence item(s)."),
            ],
            unknown=[_finding("unknown", "low", "The rationale requested is unknown.")],
        )
        passed, reason, _ = _eval(
            report, {"max_confidence": "low"})
        self.assertTrue(passed, reason)


class BackwardCompatibilityTests(unittest.TestCase):
    def test_empty_expected_passes(self) -> None:
        report = _report(observed=[_finding("observed", "high", "anything")])
        passed, reason, _ = _eval(
            report, {})
        self.assertTrue(passed, reason)

    def test_existing_classification_check_still_enforced(self) -> None:
        report = _report(unknown=[_finding("unknown", "low", "unknown")])
        passed, _, _ = _eval(
            report, {"classification": "observed"})
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
