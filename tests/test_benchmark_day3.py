"""
Day 3 adversarial failing tests for jarvis-benchmark human-readable output and filtering.

Contracts under test:
  1.  --format text prints a readable scoreboard.
  2.  Text output includes total, passed, failed, skipped.
  3.  Text output groups results by repo.
  4.  Failed questions show their failure reason.
  5.  JSON output remains valid and unchanged by default.
  6.  Each question result includes duration_seconds.
  7.  Each repo result includes duration_seconds.
  8.  Summary includes duration_seconds.
  9.  --repo filters the run to one repo.
  10. --question filters the run to one question ID.
  11. Unknown repo filter fails clearly.
  12. Unknown question filter fails clearly.

All tests here are expected to FAIL until the source is updated.
Do not change src/ to make these pass — that is Codex's job.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.benchmark import run_benchmark
from jarvis_engineering.contracts import InspectionLimits


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

ADR_BODY = """\
# ADR 001: Use in-process queue

Status: Accepted

## Context

Direct handler calls let a failure propagate into the transaction.

## Decision

We decided to use an in-process queue so that handler failures stay
outside the purchase path.

## Rationale

The team chose this approach because it avoids a network broker before
message volume justifies the operational burden.
"""

REMOTE_ALPHA = "https://github.com/example/alpha-service"
REMOTE_BETA = "https://github.com/example/beta-service"

FAST_LIMITS = InspectionLimits(
    max_files=30,
    max_file_bytes=65_536,
    max_total_bytes=2_097_152,
    max_tracked_paths=10_000,
    max_evidence_items=30,
    git_timeout_seconds=15,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_committed_repo(root: Path, name: str, remote: str, files: dict[str, str]) -> Path:
    checkout = root / name
    checkout.mkdir(parents=True)
    for rel, body in files.items():
        target = checkout / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "tests@example.com")
    _git(checkout, "config", "user.name", "JARVIS Tests")
    _git(checkout, "remote", "add", "origin", remote)
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "initial")
    return checkout


def _subprocess_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(SRC_ROOT),
        "JARVIS_PROTECTED_ROOT": str(PROJECT_ROOT.parent),
    }


# ---------------------------------------------------------------------------
# Base class with two-repo fixture
# ---------------------------------------------------------------------------

class _TwoRepoFixture(unittest.TestCase):
    """
    Creates two minimal committed repos so filter tests can assert that
    --repo and --question restrict output to only the targeted subset.

    Repo alpha  has two questions: alpha-q1 (passes) and alpha-q2 (passes).
    Repo beta   has one question:  beta-q1  (passes, expects unknown).
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.protected_root = PROJECT_ROOT.parent

        # alpha: has documented ADR
        _make_committed_repo(
            self.root,
            "alpha-service",
            REMOTE_ALPHA,
            {
                "README.md": "# Alpha\n",
                "docs/adr/001-queue.md": ADR_BODY,
            },
        )

        # beta: no ADR, honest-unknown expected
        _make_committed_repo(
            self.root,
            "beta-service",
            REMOTE_BETA,
            {
                "README.md": "# Beta\n",
                "src/cache.py": "import redis\nclient = redis.Redis()\n",
            },
        )

        self.benchmark = {
            "description": "day3 unit test",
            "repositories_root": str(self.root),
            "repos": [
                {
                    "slug": "example/alpha-service",
                    "github_url": REMOTE_ALPHA,
                    "checkout": "alpha-service",
                    "questions": [
                        {
                            "id": "alpha-q1",
                            "question": "Why does alpha-service use an in-process queue?",
                            "type": "documented-decision",
                            "expected": {
                                "classification": "observed",
                                "must_not_be_unknown": True,
                                "likely_evidence": ["docs/adr/001-queue.md"],
                            },
                        },
                        {
                            "id": "alpha-q2",
                            "question": "What is the impact of removing the queue?",
                            "type": "change-impact",
                            "supported": False,
                            "expected": {"error_code": "UNSUPPORTED_QUESTION"},
                        },
                    ],
                },
                {
                    "slug": "example/beta-service",
                    "github_url": REMOTE_BETA,
                    "checkout": "beta-service",
                    "questions": [
                        {
                            "id": "beta-q1",
                            "question": "Why does beta-service use Redis?",
                            "type": "honest-unknown",
                            "expected": {"must_report_unknown_rationale": True},
                        },
                    ],
                },
            ],
        }

        self.bench_file = self.root / "bench.json"
        self.bench_file.write_text(json.dumps(self.benchmark), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run_cli(self, extra_args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, "-m", "jarvis_engineering.benchmark",
                "--benchmark", str(self.bench_file),
                "--repositories-root", str(self.root),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )

    def _run_library(self, **kwargs) -> dict:
        return run_benchmark(
            self.benchmark,
            protected_root=self.protected_root,
            limits=FAST_LIMITS,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# 1–4: Text format output
# ---------------------------------------------------------------------------

class BenchmarkTextFormatOutputTests(_TwoRepoFixture):
    """Tests 1–4: --format text produces a human-readable scoreboard."""

    def _text_output(self) -> str:
        result = self._run_cli(["--format", "text"])
        self.assertEqual(
            result.returncode, 0,
            f"--format text must exit 0. stderr: {result.stderr}",
        )
        return result.stdout

    def test_format_text_flag_is_accepted(self) -> None:
        """FAILS: --format is not a registered argument; CLI will error."""
        result = self._run_cli(["--format", "text"])
        self.assertEqual(
            result.returncode, 0,
            f"--format text must exit 0, got {result.returncode}. stderr: {result.stderr}",
        )

    def test_text_output_is_not_json(self) -> None:
        """FAILS: current output is always JSON; text mode does not exist."""
        text = self._text_output()
        try:
            json.loads(text)
            self.fail("--format text output must not be valid JSON at the top level")
        except json.JSONDecodeError:
            pass  # expected: text output is not raw JSON

    def test_text_output_includes_scoreboard_counts(self) -> None:
        """FAILS: --format text not implemented; no scoreboard printed."""
        text = self._text_output()
        lowered = text.lower()
        self.assertIn("total", lowered, "Text scoreboard must include 'total'")
        self.assertIn("passed", lowered, "Text scoreboard must include 'passed'")
        self.assertIn("failed", lowered, "Text scoreboard must include 'failed'")
        self.assertIn("skipped", lowered, "Text scoreboard must include 'skipped'")

    def test_text_output_groups_by_repo(self) -> None:
        """FAILS: --format text not implemented; no per-repo grouping."""
        text = self._text_output()
        self.assertIn(
            "alpha-service", text,
            "Text output must include alpha-service repo slug or name",
        )
        self.assertIn(
            "beta-service", text,
            "Text output must include beta-service repo slug or name",
        )

    def test_failed_question_shows_failure_reason_in_text(self) -> None:
        """FAILS: --format text not implemented; failure reasons not surfaced."""
        # alpha-q2 is 'change-impact' but expected UNSUPPORTED_QUESTION;
        # if it passes that is fine — run a question that will definitely fail.
        bench = dict(self.benchmark)
        bench = {
            "description": "failure-reason test",
            "repositories_root": str(self.root),
            "repos": [
                {
                    "slug": "example/alpha-service",
                    "github_url": REMOTE_ALPHA,
                    "checkout": "alpha-service",
                    "questions": [
                        {
                            "id": "alpha-fail",
                            # Redis has no ADR in alpha-service; must_not_be_unknown will be violated
                            "question": "Why does alpha-service use Redis?",
                            "type": "documented-decision",
                            "expected": {
                                "classification": "observed",
                                "must_not_be_unknown": True,
                            },
                        },
                    ],
                }
            ],
        }
        fail_bench_file = self.root / "fail_bench.json"
        fail_bench_file.write_text(json.dumps(bench), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, "-m", "jarvis_engineering.benchmark",
                "--benchmark", str(fail_bench_file),
                "--repositories-root", str(self.root),
                "--format", "text",
            ],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertNotEqual(result.returncode, 0, "A benchmark run with failed questions must exit non-zero")
        text = result.stdout.lower()
        # The failure reason must appear somewhere in the text output
        self.assertTrue(
            "fail" in text or "unknown" in text or "reason" in text,
            f"Text output for a failed question must surface a failure reason. Got:\n{result.stdout[:800]}",
        )


# ---------------------------------------------------------------------------
# 5: JSON default
# ---------------------------------------------------------------------------

class BenchmarkJSONDefaultTests(_TwoRepoFixture):
    """Test 5: JSON output is valid and returned by default (no --format flag)."""

    def test_default_output_is_valid_json(self) -> None:
        """
        FAILS only if the current JSON output is broken.
        This test should already pass — it guards against regression
        while text format is added.
        """
        result = self._run_cli([])
        self.assertEqual(
            result.returncode, 0,
            f"Default CLI run must exit 0. stderr: {result.stderr}",
        )
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Default CLI output is not valid JSON: {exc}\n{result.stdout[:500]}")
        self.assertIn("repos", parsed, "Default JSON output must include 'repos'")
        self.assertIn("summary", parsed, "Default JSON output must include 'summary'")

    def test_json_flag_explicit_also_works(self) -> None:
        """FAILS: --format not registered; passing --format json must still work."""
        result = self._run_cli(["--format", "json"])
        self.assertEqual(
            result.returncode, 0,
            f"--format json must exit 0. stderr: {result.stderr}",
        )
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"--format json output is not valid JSON: {exc}")

    def test_json_output_structure_preserved_when_format_text_is_not_requested(self) -> None:
        """FAILS: guards that adding --format text does not mutate JSON default."""
        result_default = self._run_cli([])
        result_json = self._run_cli(["--format", "json"])
        # Both exit 0 and produce the same JSON structure
        self.assertEqual(result_default.returncode, 0)
        self.assertEqual(result_json.returncode, 0)
        try:
            default_parsed = json.loads(result_default.stdout)
            json_parsed = json.loads(result_json.stdout)
        except json.JSONDecodeError:
            self.fail("One or both outputs were not valid JSON")
        self.assertEqual(
            set(default_parsed.keys()),
            set(json_parsed.keys()),
            "Top-level keys must be identical for default and --format json",
        )


# ---------------------------------------------------------------------------
# 6–8: duration_seconds in results
# ---------------------------------------------------------------------------

class BenchmarkDurationSecondsTests(_TwoRepoFixture):
    """Tests 6–8: timing fields in question, repo, and summary results."""

    def setUp(self) -> None:
        super().setUp()
        self.result = self._run_library()

    def test_question_result_includes_duration_seconds(self) -> None:
        """FAILS: duration_seconds not present in _question_result output."""
        for repo in self.result["repos"]:
            for question in repo["questions"]:
                self.assertIn(
                    "duration_seconds",
                    question,
                    f"Question {question.get('id')!r} is missing 'duration_seconds'",
                )
                self.assertIsInstance(
                    question["duration_seconds"],
                    (int, float),
                    f"Question {question.get('id')!r} duration_seconds must be numeric",
                )
                self.assertGreaterEqual(
                    question["duration_seconds"],
                    0,
                    f"Question {question.get('id')!r} duration_seconds must be non-negative",
                )

    def test_repo_result_includes_duration_seconds(self) -> None:
        """FAILS: duration_seconds not present in repo result dict."""
        for repo in self.result["repos"]:
            self.assertIn(
                "duration_seconds",
                repo,
                f"Repo {repo.get('slug')!r} is missing 'duration_seconds'",
            )
            self.assertIsInstance(
                repo["duration_seconds"],
                (int, float),
                f"Repo {repo.get('slug')!r} duration_seconds must be numeric",
            )
            self.assertGreaterEqual(
                repo["duration_seconds"],
                0,
                f"Repo {repo.get('slug')!r} duration_seconds must be non-negative",
            )

    def test_summary_includes_duration_seconds(self) -> None:
        """FAILS: duration_seconds not present in summary dict."""
        summary = self.result["summary"]
        self.assertIn(
            "duration_seconds",
            summary,
            "Summary is missing 'duration_seconds'",
        )
        self.assertIsInstance(
            summary["duration_seconds"],
            (int, float),
            "Summary duration_seconds must be numeric",
        )
        self.assertGreaterEqual(
            summary["duration_seconds"],
            0,
            "Summary duration_seconds must be non-negative",
        )

    def test_skipped_repo_also_has_duration_seconds(self) -> None:
        """FAILS: _skipped_repo() does not emit duration_seconds."""
        bench = {
            "description": "skip duration test",
            "repositories_root": str(self.root),
            "repos": [
                {
                    "slug": "example/ghost",
                    "github_url": "https://github.com/example/ghost",
                    "checkout": "does_not_exist",
                    "questions": [
                        {
                            "id": "ghost-q1",
                            "question": "Why?",
                            "type": "documented-decision",
                            "expected": {"classification": "observed", "must_not_be_unknown": True},
                        }
                    ],
                }
            ],
        }
        result = run_benchmark(bench, protected_root=self.protected_root, limits=FAST_LIMITS)
        repo = result["repos"][0]
        self.assertTrue(repo.get("skipped"), "Fixture repo must be skipped")
        self.assertIn(
            "duration_seconds",
            repo,
            "Skipped repo result must still include 'duration_seconds'",
        )

    def test_duration_seconds_is_json_serialisable(self) -> None:
        """FAILS: confirms duration_seconds survives JSON round-trip."""
        try:
            json.dumps(self.result)
        except (TypeError, ValueError) as exc:
            self.fail(f"Result with duration_seconds is not JSON-serialisable: {exc}")


# ---------------------------------------------------------------------------
# 9–10: --repo and --question filter flags
# ---------------------------------------------------------------------------

class BenchmarkFilterTests(_TwoRepoFixture):
    """Tests 9–10: --repo and --question restrict the run to a subset."""

    def test_repo_filter_restricts_to_one_repo(self) -> None:
        """FAILS: --repo flag does not exist in _parser()."""
        result = self._run_cli(["--repo", "example/alpha-service"])
        self.assertEqual(
            result.returncode, 0,
            f"--repo filter must exit 0. stderr: {result.stderr}",
        )
        parsed = json.loads(result.stdout)
        slugs = [r["slug"] for r in parsed["repos"]]
        self.assertIn("example/alpha-service", slugs, "Filtered result must contain alpha-service")
        self.assertNotIn(
            "example/beta-service", slugs,
            "Filtered result must not contain beta-service when --repo alpha-service is given",
        )

    def test_repo_filter_result_has_correct_question_count(self) -> None:
        """FAILS: --repo flag does not exist; question count cannot be verified."""
        result = self._run_cli(["--repo", "example/alpha-service"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        parsed = json.loads(result.stdout)
        alpha = next(r for r in parsed["repos"] if r["slug"] == "example/alpha-service")
        self.assertEqual(
            len(alpha["questions"]),
            2,
            "alpha-service has 2 questions; all must appear when filtered by repo",
        )
        self.assertEqual(
            parsed["summary"]["total"],
            2,
            "Summary total must be 2 when filtered to alpha-service only",
        )

    def test_question_filter_restricts_to_one_question(self) -> None:
        """FAILS: --question flag does not exist in _parser()."""
        result = self._run_cli(["--question", "beta-q1"])
        self.assertEqual(
            result.returncode, 0,
            f"--question filter must exit 0. stderr: {result.stderr}",
        )
        parsed = json.loads(result.stdout)
        all_question_ids = [
            q["id"]
            for r in parsed["repos"]
            for q in r["questions"]
        ]
        self.assertIn("beta-q1", all_question_ids, "Filtered result must contain beta-q1")
        self.assertNotIn(
            "alpha-q1", all_question_ids,
            "Filtered result must not contain alpha-q1 when --question beta-q1 is given",
        )
        self.assertNotIn(
            "alpha-q2", all_question_ids,
            "Filtered result must not contain alpha-q2 when --question beta-q1 is given",
        )

    def test_question_filter_summary_total_is_one(self) -> None:
        """FAILS: --question flag does not exist; summary total cannot be verified."""
        result = self._run_cli(["--question", "alpha-q1"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        parsed = json.loads(result.stdout)
        self.assertEqual(
            parsed["summary"]["total"],
            1,
            "Summary total must be 1 when filtered to a single question",
        )

    def test_repo_and_question_filter_combined(self) -> None:
        """FAILS: neither flag exists; combined filter cannot be verified."""
        result = self._run_cli(["--repo", "example/alpha-service", "--question", "alpha-q2"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        parsed = json.loads(result.stdout)
        all_question_ids = [
            q["id"]
            for r in parsed["repos"]
            for q in r["questions"]
        ]
        self.assertEqual(
            all_question_ids,
            ["alpha-q2"],
            f"Combined --repo + --question must yield exactly [alpha-q2], got {all_question_ids}",
        )


# ---------------------------------------------------------------------------
# 11–12: Unknown filter values fail clearly
# ---------------------------------------------------------------------------

class BenchmarkUnknownFilterTests(_TwoRepoFixture):
    """Tests 11–12: unknown --repo or --question values produce a clear error."""

    def test_unknown_repo_filter_exits_nonzero(self) -> None:
        """FAILS: --repo flag does not exist; unknown value cannot be checked."""
        result = self._run_cli(["--repo", "nonexistent/no-such-repo"])
        self.assertNotEqual(
            result.returncode, 0,
            "Unknown --repo value must exit non-zero",
        )

    def test_unknown_repo_filter_prints_clear_error(self) -> None:
        """FAILS: --repo flag does not exist; no error message produced."""
        result = self._run_cli(["--repo", "nonexistent/no-such-repo"])
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "nonexistent/no-such-repo" in combined or "not found" in combined or "unknown" in combined,
            f"Error output must mention the unknown repo slug. Got:\n{result.stdout[:400]}\n{result.stderr[:400]}",
        )

    def test_unknown_question_filter_exits_nonzero(self) -> None:
        """FAILS: --question flag does not exist; unknown value cannot be checked."""
        result = self._run_cli(["--question", "no-such-question-id"])
        self.assertNotEqual(
            result.returncode, 0,
            "Unknown --question value must exit non-zero",
        )

    def test_unknown_question_filter_prints_clear_error(self) -> None:
        """FAILS: --question flag does not exist; no error message produced."""
        result = self._run_cli(["--question", "no-such-question-id"])
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "no-such-question-id" in combined or "not found" in combined or "unknown" in combined,
            f"Error output must mention the unknown question ID. Got:\n{result.stdout[:400]}\n{result.stderr[:400]}",
        )

    def test_unknown_repo_with_valid_question_still_fails(self) -> None:
        """FAILS: --repo flag does not exist; combined unknown-valid must still error."""
        result = self._run_cli(["--repo", "nonexistent/repo", "--question", "alpha-q1"])
        self.assertNotEqual(
            result.returncode, 0,
            "An unknown --repo must cause non-zero exit even when --question is valid",
        )

    def test_unknown_question_with_valid_repo_still_fails(self) -> None:
        """FAILS: --question flag does not exist; valid-repo + unknown question must error."""
        result = self._run_cli(["--repo", "example/alpha-service", "--question", "no-such-id"])
        self.assertNotEqual(
            result.returncode, 0,
            "An unknown --question must cause non-zero exit even when --repo is valid",
        )


if __name__ == "__main__":
    unittest.main()
