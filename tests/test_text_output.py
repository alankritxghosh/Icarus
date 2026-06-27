from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sample_repo"

import sys

sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering import cli
from jarvis_engineering.inspector import inspect_repository
from jarvis_engineering.render import render_text_report


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class TextOutputTests(unittest.TestCase):
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

    def _report(self, question: str) -> dict:
        return inspect_repository(
            "https://github.com/example/checkout-service",
            "sample",
            str(self.root),
            question,
            protected_root=PROJECT_ROOT.parent,
        )

    def test_text_report_contains_answer_evidence_and_limits(self) -> None:
        text = render_text_report(self._report("Why does checkout use an in-process event bus?"))

        self.assertIn("Answer:", text)
        self.assertIn("Evidence:", text)
        self.assertIn("docs/adr/0001-event-bus.md", text)
        self.assertIn("Limits:", text)
        self.assertIn("Use --format json", text)

    def test_text_report_is_honest_when_rationale_is_unknown(self) -> None:
        text = render_text_report(self._report("Why does checkout use Redis?"))

        self.assertIn("cannot prove the requested rationale", text)
        self.assertIn("src/checkout/cache.py", text)
        self.assertIn("unknown because no relevant explicit decision-and-reason language was found", text)

    def test_cli_format_text_emits_human_readable_report(self) -> None:
        output = io.StringIO()
        with (
            mock.patch("sys.stdout", output),
            mock.patch.dict(os.environ, {"JARVIS_PROTECTED_ROOT": str(PROJECT_ROOT.parent)}),
        ):
            exit_code = cli.main(
                [
                    "https://github.com/example/checkout-service",
                    "sample",
                    "Why does checkout use an in-process event bus?",
                    "--repositories-root",
                    str(self.root),
                    "--format",
                    "text",
                ]
            )

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("Answer:", rendered)
        self.assertIn("Evidence:", rendered)
        self.assertNotIn('"ok": true', rendered)

    def test_cli_no_args_starts_repo_chat(self) -> None:
        output = io.StringIO()
        with (
            mock.patch("sys.stdout", output),
            mock.patch("builtins.input", side_effect=["Why does checkout use an in-process event bus?", "exit"]),
            mock.patch("pathlib.Path.cwd", return_value=self.checkout),
            mock.patch("jarvis_engineering.cli._default_protected_root", return_value=PROJECT_ROOT.parent),
        ):
            exit_code = cli.main([])

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("JARVIS Engineering online", rendered)
        self.assertIn("Answer:", rendered)
        self.assertIn("Evidence:", rendered)
        self.assertIn("docs/adr/0001-event-bus.md", rendered)

    def test_specific_question_term_beats_common_repository_name(self) -> None:
        root = self.root / "focused"
        checkout = root / "backstage"
        checkout.mkdir(parents=True)
        for index in range(8):
            path = checkout / "beps" / f"{index:04d}" / "README.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "Backstage proposal\n\n"
                "Decision: Backstage adopted a general architecture proposal.\n"
                "Rationale: because Backstage needed a documented operating model.\n",
                encoding="utf-8",
            )
        luxon = checkout / "docs" / "decisions" / "0009-luxon.md"
        luxon.parent.mkdir(parents=True)
        luxon.write_text(
            "Decision: Backstage chose Luxon for date handling.\n"
            "Rationale: because it provided timezone-aware APIs with clearer migration behavior.\n",
            encoding="utf-8",
        )
        _git(checkout, "init", "-q")
        _git(checkout, "config", "user.email", "tests@example.com")
        _git(checkout, "config", "user.name", "JARVIS Tests")
        _git(checkout, "remote", "add", "origin", "https://github.com/example/backstage.git")
        _git(checkout, "add", ".")
        _git(checkout, "commit", "-qm", "fixture")

        report = inspect_repository(
            "https://github.com/example/backstage",
            "backstage",
            str(root),
            "Why did Backstage choose Luxon?",
            protected_root=PROJECT_ROOT.parent,
        )
        text = render_text_report(report)

        self.assertIn("docs/decisions/0009-luxon.md", text)
        self.assertIn("timezone-aware APIs", text)


if __name__ == "__main__":
    unittest.main()
