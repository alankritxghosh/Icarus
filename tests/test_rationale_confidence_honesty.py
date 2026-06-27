"""
Honesty regression: a "why" question whose rationale is genuinely absent must
not also produce a HIGH-confidence finding that claims decision-and-rationale
language was found.

This reproduces the §7 P1 false-confidence contradiction surfaced by the
govuk-color-palette-unknown benchmark question: the inspector emitted both
  - unknown/low  "The rationale requested ... is unknown"
  - observed/high "Decision and rationale language occur near each other ..."
for the same question, because the repo-wide rationale scan fired even though
none of that language was relevant to the question asked.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.inspector import inspect_repository

from test_benchmark_runner import _make_committed_repo


# A doc that DOES contain explicit decision + rationale language, but about
# queues — unrelated to the colour question we will ask.
QUEUE_ADR = """\
# ADR 001: Use an in-process queue

## Decision

We decided to use an in-process queue.

## Rationale

The team chose this because a network broker adds operational burden before
message volume justifies it.
"""


class RationaleConfidenceHonestyTests(unittest.TestCase):
    GITHUB_URL = "https://github.com/example/palette-site"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _make_committed_repo(
            self.root,
            "palette-site",
            self.GITHUB_URL,
            {
                "README.md": "# Palette Site\n\nA website.\n",
                "docs/adr/001-queue.md": QUEUE_ADR,
                "src/app.py": "print('hello')\n",
            },
        )
        self.protected_root = PROJECT_ROOT.parent

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _report(self, question: str) -> dict:
        return inspect_repository(
            self.GITHUB_URL,
            "palette-site",
            str(self.root),
            question,
            protected_root=self.protected_root,
        )

    def _findings(self, report: dict) -> list[dict]:
        return [f for group in report["findings"].values() for f in group]

    def test_unknown_rationale_question_has_no_high_confidence_rationale_finding(self) -> None:
        # Ask "why" about colours — the repo has rationale language, but only
        # about queues, so this question's rationale is genuinely unknown.
        report = self._report("Why was the colour palette chosen the way it is?")
        findings = self._findings(report)

        unknown_rationale = [
            f for f in report["findings"]["unknown"]
            if "rationale" in f["statement"].casefold() and "unknown" in f["statement"].casefold()
        ]
        self.assertTrue(
            unknown_rationale,
            "Expected an honest unknown-rationale finding for an undocumented 'why' question",
        )

        high_rationale = [
            f for f in findings
            if "rationale" in f["statement"].casefold() and f["confidence"] == "high"
        ]
        self.assertEqual(
            high_rationale,
            [],
            "Must not emit a high-confidence rationale finding while declaring the "
            f"rationale unknown. Offending findings: {[f['statement'] for f in high_rationale]}",
        )

    def test_relevant_rationale_question_still_reports_high_confidence(self) -> None:
        # Control: when the question IS about the documented decision, the
        # high-confidence relevant-rationale finding must still appear.
        report = self._report("Why does the service use an in-process queue?")
        high_rationale = [
            f for group in report["findings"].values() for f in group
            if "rationale" in f["statement"].casefold() and f["confidence"] == "high"
        ]
        self.assertTrue(
            high_rationale,
            "A documented, relevant rationale question should still yield a high-confidence finding",
        )


if __name__ == "__main__":
    unittest.main()
