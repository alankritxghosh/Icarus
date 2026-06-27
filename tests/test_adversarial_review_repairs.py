from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

import sys

sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering import benchmark, cli
from jarvis_engineering.contracts import ErrorCode, InspectionError, InspectionLimits
from jarvis_engineering.inspector import _asks_unsupported_reasoning, inspect_repository


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_repo(root: Path, name: str, remote: str = "https://github.com/example/repo") -> Path:
    checkout = root / name
    checkout.mkdir(parents=True)
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "tests@example.com")
    _git(checkout, "config", "user.name", "JARVIS Tests")
    _git(checkout, "remote", "add", "origin", remote)
    return checkout


def _commit(checkout: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        target = checkout / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "fixture")


class ExplicitProtectedRootTests(unittest.TestCase):
    def test_cli_fails_closed_without_env_protected_root(self) -> None:
        buf = io.StringIO()
        with (
            mock.patch("sys.stdout", buf),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            exit_code = cli.main(["What is the architecture?"])
        report = json.loads(buf.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["error"]["code"], ErrorCode.PROTECTED_ROOT_ACCESS)

    def test_benchmark_fails_closed_without_env_or_argument_protected_root(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(InspectionError) as caught:
                benchmark.run_benchmark({"repositories_root": "/tmp", "repos": []})
        self.assertEqual(caught.exception.code, ErrorCode.PROTECTED_ROOT_ACCESS)


class UnsupportedQuestionBypassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = _make_repo(self.root, "repo")
        _commit(self.checkout, {"README.md": "# Repo\n\nArchitecture notes.\n"})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_unsupported(self, question: str) -> None:
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                "https://github.com/example/repo",
                "repo",
                str(self.root),
                question,
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.UNSUPPORTED_QUESTION)

    def assert_supported(self, question: str) -> None:
        report = inspect_repository(
            "https://github.com/example/repo",
            "repo",
            str(self.root),
            question,
            protected_root=PROJECT_ROOT.parent,
        )
        self.assertTrue(report["ok"])

    def test_rely_on_bypass_is_refused(self) -> None:
        self.assert_unsupported("What components rely on the event bus?")

    def test_dependent_on_bypass_is_refused(self) -> None:
        self.assert_unsupported("What is dependent on the cache module?")

    def test_affected_when_deleted_bypass_is_refused(self) -> None:
        self.assert_unsupported("What is affected when the cache is deleted?")

    def test_ripple_effect_bypass_is_refused(self) -> None:
        self.assert_unsupported("What is the ripple effect of removing the queue?")

    def test_retrospective_removed_decision_question_is_supported(self) -> None:
        self.assert_supported("Why did the team remove Python 2 support?")

    def test_retrospective_deleted_decision_question_is_supported(self) -> None:
        self.assert_supported("Why does the project redirect deleted URLs instead of leaving them broken?")

    def test_retrospective_dropped_decision_question_is_supported(self) -> None:
        self.assert_supported("Why did they drop support for Node 14?")

    def test_hypothetical_remove_impact_is_still_refused(self) -> None:
        self.assert_unsupported("What happens if we remove the queue?")

    def test_breaks_after_removing_is_refused(self) -> None:
        self.assert_unsupported("What breaks after removing node-fetch?")

    def test_services_break_after_removed_is_refused(self) -> None:
        self.assert_unsupported("What other services break after node-fetch is removed?")

    def test_needs_updating_after_remove_is_refused(self) -> None:
        self.assert_unsupported("What needs updating after we remove the queue?")

    def test_after_removing_stops_working_is_refused(self) -> None:
        self.assert_unsupported("After removing the cache, what stops working?")

    # Reverse-dependency / impact phrasings (inflections and connectives).

    def test_impacted_by_removing_is_refused(self) -> None:
        self.assert_unsupported("Which modules are impacted by removing the queue?")

    def test_affected_by_dropping_is_refused(self) -> None:
        self.assert_unsupported("Show me everything affected by dropping Node 14.")

    def test_relying_on_is_refused(self) -> None:
        self.assert_unsupported("What is relying on the event bus?")

    def test_consumed_is_refused(self) -> None:
        self.assert_unsupported("What consumed the old API?")

    def test_imports_is_refused(self) -> None:
        self.assert_unsupported("What modules import the queue?")

    def test_who_calls_is_refused(self) -> None:
        self.assert_unsupported("Who calls the checkout endpoint?")

    def test_reverse_uses_is_refused(self) -> None:
        self.assert_unsupported("What uses the queue?")

    def test_reverse_uses_with_subject_is_refused(self) -> None:
        self.assert_unsupported("Which services use Redis?")

    def test_impacted_by_deleting_is_refused(self) -> None:
        self.assert_unsupported("What is impacted by deleting the cache?")

    def test_impacts_of_removing_is_refused(self) -> None:
        self.assert_unsupported("What are the impacts of removing node-fetch?")

    # Supported decision questions that an over-tuned gate falsely refused. These must stay
    # answerable: refusing them violates the core V1 promise.

    def test_rationale_for_using_is_supported(self) -> None:
        self.assert_supported("What is the rationale for Flask using context locals and proxies?")

    def test_why_does_service_use_is_supported(self) -> None:
        self.assert_supported("Why does the service use an in-process queue?")

    def test_why_changed_to_use_is_supported(self) -> None:
        self.assert_supported("Why was the auth module changed to use tokens?")

    def test_what_database_does_service_use_is_supported(self) -> None:
        self.assert_supported("What database does the service use?")

    def test_why_component_fails_closed_is_supported(self) -> None:
        self.assert_supported("Why does this component fail closed on startup?")

    def test_consequences_of_choosing_is_supported(self) -> None:
        self.assert_supported("What were the consequences of choosing Luxon?")


class BenchmarkGateConsistencyTests(unittest.TestCase):
    """The intent gate must agree with the benchmark's supported/unsupported labels."""

    def setUp(self) -> None:
        with (PROJECT_ROOT / "benchmarks" / "large_repos.json").open(encoding="utf-8") as handle:
            self.data = json.load(handle)

    def test_supported_questions_are_not_refused(self) -> None:
        for repo in self.data["repos"]:
            for question in repo["questions"]:
                if question.get("supported") is False:
                    continue
                with self.subTest(question=question["id"]):
                    self.assertFalse(
                        _asks_unsupported_reasoning(question["question"]),
                        f"supported benchmark question {question['id']!r} was refused by the gate",
                    )

    def test_unsupported_impact_questions_are_refused(self) -> None:
        for repo in self.data["repos"]:
            for question in repo["questions"]:
                if question.get("supported") is not False:
                    continue
                # Isolation-traversal questions are blocked earlier by the brain/ guard,
                # not by the change-impact reasoning gate.
                if question["expected"].get("error_code") != "UNSUPPORTED_QUESTION":
                    continue
                with self.subTest(question=question["id"]):
                    self.assertTrue(
                        _asks_unsupported_reasoning(question["question"]),
                        f"unsupported benchmark question {question['id']!r} slipped through the gate",
                    )


class GitlinkSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = _make_repo(self.root, "repo")
        _commit(
            self.checkout,
            {
                "docs/adr/001.md": (
                    "# ADR 001\n\nDecision: Use a queue.\n\n"
                    "Rationale: because handlers should not block checkout.\n"
                )
            },
        )
        _git(
            self.checkout,
            "update-index",
            "--add",
            "--cacheinfo",
            "160000,0123456789012345678901234567890123456789,.github/workflows/build.yml",
        )
        _git(self.checkout, "commit", "-qm", "add gitlink")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_gitlink_entry_does_not_abort_inspection(self) -> None:
        report = inspect_repository(
            "https://github.com/example/repo",
            "repo",
            str(self.root),
            "Why use a queue?",
            protected_root=PROJECT_ROOT.parent,
            limits=InspectionLimits(max_files=20, max_tracked_paths=100),
        )
        self.assertTrue(report["ok"])
        self.assertFalse(any(item["path"] == ".github/workflows/build.yml" for item in report["evidence"]))


class ProtectedRootConfigurationWarningTests(unittest.TestCase):
    def test_warns_when_protected_root_is_inside_repositories_root(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            checkout = _make_repo(root, "repo")
            _commit(checkout, {"README.md": "# Repo\n\nArchitecture notes.\n"})
            protected = root / "too-narrow-protected-root"
            protected.mkdir()

            report = inspect_repository(
                "https://github.com/example/repo",
                "repo",
                str(root),
                "Why was this architecture chosen?",
                protected_root=protected,
            )

            self.assertIn(
                "The configured protected root is inside repositories_root; personal-workspace protection may be too narrow.",
                report["warnings"],
            )
        finally:
            temp.cleanup()


class BenchmarkWarningSurfaceTests(unittest.TestCase):
    def test_benchmark_json_carries_protected_root_warning(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            checkout = _make_repo(root, "repo")
            _commit(checkout, {"README.md": "# Repo\n\nArchitecture notes.\n"})
            protected = root / "too-narrow-protected-root"
            protected.mkdir()
            bench = {
                "repositories_root": str(root),
                "repos": [
                    {
                        "slug": "example/repo",
                        "github_url": "https://github.com/example/repo",
                        "checkout": "repo",
                        "questions": [
                            {
                                "id": "q1",
                                "question": "Why was this architecture chosen?",
                                "type": "documented-decision",
                                "expected": {"classification": "observed"},
                            }
                        ],
                    }
                ],
            }

            result = benchmark.run_benchmark(bench, protected_root=protected)

            warning = "The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."
            self.assertIn(warning, result["warnings"])
            self.assertIn(warning, result["safety_warnings"])
            self.assertIn(warning, result["summary"]["warnings"])
            self.assertIn(warning, result["summary"]["safety_warnings"])
            self.assertIn(warning, result["repos"][0]["warnings"])
            self.assertIn(warning, result["repos"][0]["safety_warnings"])
            self.assertIn(warning, result["repos"][0]["questions"][0]["warnings"])
            self.assertIn(warning, result["repos"][0]["questions"][0]["safety_warnings"])
        finally:
            temp.cleanup()

    def test_benchmark_text_carries_protected_root_warning(self) -> None:
        result = {
            "summary": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 0.1,
                "warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
                "safety_warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
            },
            "warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
            "safety_warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
            "repos": [
                {
                    "slug": "example/repo",
                    "skipped": False,
                    "skip_reason": None,
                    "duration_seconds": 0.1,
                    "warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
                    "safety_warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
                    "questions": [
                        {
                            "id": "q1",
                            "passed": True,
                            "skipped": False,
                            "duration_seconds": 0.1,
                            "warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
                            "safety_warnings": ["The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."],
                        }
                    ],
                }
            ],
        }

        text = benchmark.render_text_result(result)

        self.assertIn("Safety warnings:", text)
        self.assertIn("protected root is inside repositories_root", text)

    def test_benchmark_text_does_not_promote_routine_warnings(self) -> None:
        result = {
            "summary": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 0.1,
                "warnings": ["Public reachability was not checked; the GitHub URL was validated syntactically only."],
                "safety_warnings": [],
            },
            "warnings": ["Public reachability was not checked; the GitHub URL was validated syntactically only."],
            "safety_warnings": [],
            "repos": [
                {
                    "slug": "example/repo",
                    "skipped": False,
                    "skip_reason": None,
                    "duration_seconds": 0.1,
                    "warnings": ["Public reachability was not checked; the GitHub URL was validated syntactically only."],
                    "safety_warnings": [],
                    "questions": [
                        {
                            "id": "q1",
                            "passed": True,
                            "skipped": False,
                            "duration_seconds": 0.1,
                            "warnings": ["Public reachability was not checked; the GitHub URL was validated syntactically only."],
                            "safety_warnings": [],
                        }
                    ],
                }
            ],
        }

        text = benchmark.render_text_result(result)

        self.assertNotIn("Safety warnings:", text)
        self.assertNotIn("Public reachability was not checked", text)


class BenchmarkExitCodeTests(unittest.TestCase):
    def test_cli_returns_nonzero_when_questions_fail(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            checkout = _make_repo(root, "repo")
            _commit(checkout, {"README.md": "# Repo\n"})
            bench = {
                "repositories_root": str(root),
                "repos": [
                    {
                        "slug": "example/repo",
                        "github_url": "https://github.com/example/repo",
                        "checkout": "repo",
                        "questions": [
                            {
                                "id": "missing-rationale",
                                "question": "Why does repo use Redis?",
                                "type": "documented-decision",
                                "expected": {"must_not_be_unknown": True},
                            }
                        ],
                    }
                ],
            }
            path = root / "bench.json"
            path.write_text(json.dumps(bench), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jarvis_engineering.benchmark",
                    "--benchmark",
                    str(path),
                    "--repositories-root",
                    str(root),
                    "--format",
                    "text",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PYTHONPATH": str(SRC_ROOT),
                    "JARVIS_PROTECTED_ROOT": str(PROJECT_ROOT.parent),
                },
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAIL", result.stdout)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
