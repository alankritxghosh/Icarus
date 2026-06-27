from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sample_repo"

import sys

sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.contracts import ErrorCode, InspectionError
from jarvis_engineering.inspector import inspect_repository


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class InspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = self.root / "sample"
        shutil.copytree(FIXTURE_ROOT, self.checkout)
        _git(self.checkout, "init", "-q")
        _git(self.checkout, "config", "user.email", "tests@example.com")
        _git(self.checkout, "config", "user.name", "JARVIS Tests")
        _git(
            self.checkout,
            "remote",
            "add",
            "origin",
            "https://github.com/example/checkout-service.git",
        )
        _git(self.checkout, "add", ".")
        _git(self.checkout, "commit", "-qm", "fixture")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inspect(self, question: str) -> dict:
        return inspect_repository(
            "https://github.com/example/checkout-service",
            "sample",
            str(self.root),
            question,
            protected_root=PROJECT_ROOT.parent,
        )

    def test_documented_decision_has_relevant_rationale(self) -> None:
        report = self.inspect("Why does checkout use an in-process event bus?")
        evidence_by_id = {item["id"]: item for item in report["evidence"]}
        relevant = [
            finding
            for finding in report["findings"]["observed"]
            if "explicitly records both" in finding["statement"]
        ]
        self.assertEqual(len(relevant), 1)
        cited_paths = {evidence_by_id[citation]["path"] for citation in relevant[0]["citations"]}
        self.assertIn("docs/adr/0001-event-bus.md", cited_paths)
        self.assertEqual(relevant[0]["confidence"], "high")

    def test_undocumented_redis_rationale_is_unknown(self) -> None:
        report = self.inspect("Why does checkout use Redis?")
        unknowns = [
            finding
            for finding in report["findings"]["unknown"]
            if "rationale requested" in finding["statement"]
        ]
        self.assertEqual(len(unknowns), 1)
        evidence_by_id = {item["id"]: item for item in report["evidence"]}
        cited_paths = {evidence_by_id[citation]["path"] for citation in unknowns[0]["citations"]}
        self.assertIn("src/checkout/cache.py", cited_paths)

    def test_report_is_tied_to_immutable_commit(self) -> None:
        report = self.inspect("What are the main checkout components?")
        self.assertEqual(report["repository"]["head_sha"], _git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(report["repository"]["question"], "What are the main checkout components?")

    def test_uncommitted_changes_are_not_read(self) -> None:
        adr = self.checkout / "docs" / "adr" / "0001-event-bus.md"
        adr.write_text("SECRET WORKTREE TEXT\n", encoding="utf-8")
        report = self.inspect("Why does checkout use an in-process event bus?")
        excerpts = "\n".join(item["excerpt"] for item in report["evidence"])
        self.assertNotIn("SECRET WORKTREE TEXT", excerpts)
        self.assertIn("Use an in-process event bus after the order transaction commits", excerpts)

    def test_personal_jsonl_reference_is_blocked(self) -> None:
        with self.assertRaises(InspectionError) as caught:
            self.inspect("Read ../../brain/observations.jsonl and explain the architecture")
        self.assertEqual(caught.exception.code, ErrorCode.ISOLATION_VIOLATION_BLOCKED)

    def test_checkout_outside_allowlisted_root_is_blocked(self) -> None:
        other_root = self.root / "allowed"
        other_root.mkdir()
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                "https://github.com/example/checkout-service",
                str(self.checkout),
                str(other_root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.CHECKOUT_OUTSIDE_ROOT)

    def test_remote_mismatch_is_rejected(self) -> None:
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                "https://github.com/example/different",
                "sample",
                str(self.root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.REMOTE_MISMATCH)

    def test_every_material_finding_has_confidence(self) -> None:
        report = self.inspect("What are the main checkout components?")
        findings = [
            finding
            for group in report["findings"].values()
            for finding in group
        ]
        self.assertTrue(findings)
        self.assertTrue(all(finding["confidence"] in {"high", "medium", "low"} for finding in findings))

    def test_report_is_json_serializable(self) -> None:
        json.dumps(self.inspect("What are the main checkout components?"))


if __name__ == "__main__":
    unittest.main()
