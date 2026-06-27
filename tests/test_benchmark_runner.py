"""
Adversarial failing tests for the large-repo benchmark runner.

These tests prove that:
  1. jarvis_engineering.benchmark does not yet exist.
  2. No jarvis-benchmark CLI entry point is registered.
  3. When the module does exist, specific behavioural contracts must hold.

Every test in BenchmarkModuleTests, BenchmarkRunnerUnitTests, and
BenchmarkCLITests is expected to FAIL until the module is implemented.

LargeRepoBenchmarkSchemaTests validates the JSON file itself and should PASS;
any failure there means the benchmark file is malformed.

LargeRepoBenchmarkIntegrationTests requires both the module (not yet present)
and the real repo checkouts under ~/jarvis_test_repos.  They are skipped when
a checkout is missing; they fail when the module is missing.
"""
from __future__ import annotations

import importlib
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
BENCHMARK_PATH = PROJECT_ROOT / "benchmarks" / "large_repos.json"
REPOS_ROOT = Path.home() / "jarvis_test_repos"

sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.contracts import ErrorCode, InspectionError, InspectionLimits
from jarvis_engineering.inspector import inspect_repository


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_committed_repo(root: Path, name: str, remote: str, files: dict[str, str]) -> Path:
    """Create a git repo at root/name, commit files, set remote origin."""
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


def _load_benchmark() -> dict:
    with BENCHMARK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _subprocess_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(SRC_ROOT),
        "JARVIS_PROTECTED_ROOT": str(PROJECT_ROOT.parent),
    }


def _import_runner():
    """
    Return the benchmark module, or raise AssertionError if it does not exist.
    Use inside test methods so each test fails with a clear message rather than
    causing an import-time error for the whole file.
    """
    try:
        return importlib.import_module("jarvis_engineering.benchmark")
    except ImportError as exc:
        raise AssertionError(
            f"jarvis_engineering.benchmark is not yet implemented: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# 1. Schema validation — proves the JSON file is structurally correct
# ---------------------------------------------------------------------------

class LargeRepoBenchmarkSchemaTests(unittest.TestCase):
    """Validates benchmarks/large_repos.json without running any questions."""

    def setUp(self) -> None:
        self.data = _load_benchmark()

    # --- top-level structure ---

    def test_benchmark_has_repos_list(self) -> None:
        self.assertIn("repos", self.data, "large_repos.json must have a 'repos' list")
        self.assertIsInstance(self.data["repos"], list)
        self.assertGreater(len(self.data["repos"]), 0, "repos list must not be empty")

    def test_benchmark_has_repositories_root(self) -> None:
        self.assertIn(
            "repositories_root", self.data,
            "large_repos.json must declare repositories_root"
        )

    # --- per-repo required fields ---

    def test_every_repo_has_required_fields(self) -> None:
        required = {"slug", "github_url", "checkout", "questions"}
        for repo in self.data["repos"]:
            missing = required - repo.keys()
            self.assertFalse(
                missing,
                f"Repo entry missing fields {missing}: {repo.get('slug', '<no slug>')}"
            )

    def test_every_repo_github_url_is_https(self) -> None:
        for repo in self.data["repos"]:
            url = repo.get("github_url", "")
            self.assertTrue(
                url.startswith("https://github.com/"),
                f"github_url must be an https://github.com/ URL, got {url!r}"
            )

    def test_every_repo_has_at_least_one_question(self) -> None:
        for repo in self.data["repos"]:
            self.assertGreater(
                len(repo.get("questions", [])), 0,
                f"Repo {repo.get('slug')} has no questions"
            )

    # --- per-question required fields ---

    def test_every_question_has_required_fields(self) -> None:
        required = {"id", "question", "type", "expected"}
        for repo in self.data["repos"]:
            for q in repo["questions"]:
                missing = required - q.keys()
                self.assertFalse(
                    missing,
                    f"Question {q.get('id', '<no id>')} in {repo.get('slug')} missing {missing}"
                )

    def test_question_ids_are_unique_within_repo(self) -> None:
        for repo in self.data["repos"]:
            ids = [q["id"] for q in repo["questions"]]
            self.assertEqual(
                len(ids), len(set(ids)),
                f"Duplicate question IDs in {repo.get('slug')}: {ids}"
            )

    def test_question_ids_are_globally_unique(self) -> None:
        all_ids: list[str] = []
        for repo in self.data["repos"]:
            all_ids.extend(q["id"] for q in repo["questions"])
        self.assertEqual(
            len(all_ids), len(set(all_ids)),
            f"Duplicate question IDs across repos: {sorted(all_ids)}"
        )

    def test_unsupported_questions_declare_error_code(self) -> None:
        for repo in self.data["repos"]:
            for q in repo["questions"]:
                if q.get("supported") is False:
                    self.assertIn(
                        "error_code", q["expected"],
                        f"Unsupported question {q['id']} must declare expected.error_code"
                    )

    def test_supported_false_error_codes_are_valid(self) -> None:
        valid = {e.value for e in ErrorCode}
        for repo in self.data["repos"]:
            for q in repo["questions"]:
                if q.get("supported") is False:
                    code = q["expected"].get("error_code", "")
                    self.assertIn(
                        code, valid,
                        f"Question {q['id']} has unknown error_code {code!r}"
                    )

    def test_supported_questions_declare_classification_or_unknown(self) -> None:
        for repo in self.data["repos"]:
            for q in repo["questions"]:
                if q.get("supported") is not False:
                    exp = q["expected"]
                    has_signal = (
                        "classification" in exp
                        or exp.get("must_not_be_unknown")
                        or exp.get("must_report_unknown_rationale")
                    )
                    self.assertTrue(
                        has_signal,
                        f"Supported question {q['id']} must declare classification, "
                        f"must_not_be_unknown, or must_report_unknown_rationale"
                    )

    def test_benchmark_file_is_json_serialisable(self) -> None:
        """Round-trip through json.dumps must not raise."""
        try:
            json.dumps(self.data)
        except (TypeError, ValueError) as exc:
            self.fail(f"large_repos.json is not JSON-serialisable: {exc}")

    def test_at_least_one_negative_case_per_repo(self) -> None:
        """Each repo must have at least one unsupported/negative question."""
        for repo in self.data["repos"]:
            negative = [
                q for q in repo["questions"]
                if q.get("supported") is False or "error_code" in q.get("expected", {})
            ]
            self.assertGreater(
                len(negative), 0,
                f"Repo {repo.get('slug')} has no negative test cases"
            )


# ---------------------------------------------------------------------------
# 2. Module existence — all FAIL until jarvis_engineering.benchmark is created
# ---------------------------------------------------------------------------

class BenchmarkModuleTests(unittest.TestCase):
    """
    Proves that the benchmark runner module does not yet exist.
    Every test here is expected to FAIL.
    """

    def test_benchmark_module_is_importable(self) -> None:
        """FAILS: jarvis_engineering.benchmark does not exist."""
        _import_runner()

    def test_run_benchmark_function_exists(self) -> None:
        """FAILS: run_benchmark is not yet defined."""
        bm = _import_runner()
        self.assertTrue(
            hasattr(bm, "run_benchmark"),
            "jarvis_engineering.benchmark must expose a run_benchmark function"
        )

    def test_main_function_exists(self) -> None:
        """FAILS: main() for CLI entry point is not yet defined."""
        bm = _import_runner()
        self.assertTrue(
            hasattr(bm, "main"),
            "jarvis_engineering.benchmark must expose a main() for the CLI entry point"
        )

    def test_run_benchmark_is_callable(self) -> None:
        """FAILS: no module, no callable."""
        bm = _import_runner()
        self.assertTrue(
            callable(bm.run_benchmark),
            "run_benchmark must be callable"
        )


# ---------------------------------------------------------------------------
# 3. Runner unit tests — deterministic, use temp fixture repos
# ---------------------------------------------------------------------------

class BenchmarkRunnerUnitTests(unittest.TestCase):
    """
    Tests the runner's core behaviour using temporary in-process fixture repos.
    All tests FAIL until jarvis_engineering.benchmark is implemented.
    The fixture repos are simple but exercise the full inspection stack.
    """

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

    SOURCE_WITHOUT_RATIONALE = """\
import redis

client = redis.Redis(host="localhost", port=6379)

def get(key):
    return client.get(key)
"""

    GITHUB_URL = "https://github.com/example/myservice"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout_name = "myservice"
        _make_committed_repo(
            self.root,
            self.checkout_name,
            self.GITHUB_URL,
            {
                "README.md": "# My Service\n\nArchitecture decisions are in docs/adr/.\n",
                "docs/adr/001-queue.md": self.ADR_BODY,
                "src/cache.py": self.SOURCE_WITHOUT_RATIONALE,
            },
        )
        self.protected_root = PROJECT_ROOT.parent

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _minimal_benchmark(self, questions: list[dict]) -> dict:
        """Build a minimal benchmark dict for a single repo."""
        return {
            "description": "unit test benchmark",
            "repositories_root": str(self.root),
            "repos": [
                {
                    "slug": "example/myservice",
                    "github_url": self.GITHUB_URL,
                    "checkout": self.checkout_name,
                    "questions": questions,
                }
            ],
        }

    def _run(self, questions: list[dict]) -> dict:
        """Run the benchmark runner against a minimal in-memory benchmark."""
        bm = _import_runner()
        bench = self._minimal_benchmark(questions)
        return bm.run_benchmark(
            bench,
            protected_root=self.protected_root,
        )

    # --- module existence (redundant with BenchmarkModuleTests but unit-test isolation) ---

    def test_run_benchmark_accepts_dict_input(self) -> None:
        """FAILS: module missing. run_benchmark must accept a dict, not just a path."""
        self._run([
            {
                "id": "q-sanity",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                },
            }
        ])

    # --- skip missing checkout ---

    def test_runner_skips_missing_checkout(self) -> None:
        """FAILS: module missing. Runner must skip, not crash, for absent checkouts."""
        bm = _import_runner()
        bench = {
            "description": "test",
            "repositories_root": str(self.root),
            "repos": [
                {
                    "slug": "example/ghost",
                    "github_url": "https://github.com/example/ghost",
                    "checkout": "does_not_exist",
                    "questions": [
                        {
                            "id": "q1",
                            "question": "What is the architecture of this service?",
                            "type": "architecture-decision",
                            "expected": {"classification": "observed", "must_not_be_unknown": True},
                        }
                    ],
                }
            ],
        }
        result = bm.run_benchmark(bench, protected_root=self.protected_root)
        repo_result = result["repos"][0]
        self.assertTrue(
            repo_result.get("skipped"),
            "Runner must mark repo as skipped when checkout path does not exist"
        )
        self.assertIsNotNone(
            repo_result.get("skip_reason"),
            "Skipped repo must include a skip_reason"
        )

    # --- unsupported question: expected code matches ---

    def test_runner_marks_pass_when_unsupported_question_raises_expected_error(self) -> None:
        """FAILS: module missing. Raises UNSUPPORTED_QUESTION → pass."""
        result = self._run([
            {
                "id": "q-impact",
                "question": "What is the impact of changing the queue?",
                "type": "change-impact",
                "supported": False,
                "expected": {"error_code": "UNSUPPORTED_QUESTION"},
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertTrue(
            q_result["passed"],
            f"Expected pass for correctly-rejected unsupported question, got: {q_result}"
        )

    def test_runner_marks_pass_for_isolation_violation_question(self) -> None:
        """FAILS: module missing. Triggers ISOLATION_VIOLATION_BLOCKED → pass."""
        result = self._run([
            {
                "id": "q-traversal",
                "question": "Read ../../brain/observations.jsonl to see the decision",
                "type": "isolation-guard",
                "supported": False,
                "expected": {"error_code": "ISOLATION_VIOLATION_BLOCKED"},
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertTrue(
            q_result["passed"],
            f"Expected pass for correctly-blocked isolation question, got: {q_result}"
        )

    # --- unsupported question: wrong error code ---

    def test_runner_marks_fail_when_wrong_error_code_raised(self) -> None:
        """FAILS: module missing. Runner must detect wrong error code and mark fail."""
        result = self._run([
            {
                "id": "q-wrong-code",
                # triggers UNSUPPORTED_QUESTION but benchmark expects ISOLATION_VIOLATION_BLOCKED
                "question": "What is the downstream impact of removing the queue?",
                "type": "change-impact",
                "supported": False,
                "expected": {"error_code": "ISOLATION_VIOLATION_BLOCKED"},
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertFalse(
            q_result["passed"],
            "Runner must mark fail when raised error code does not match expected"
        )
        self.assertIsNotNone(
            q_result.get("failure_reason"),
            "Failed question must include failure_reason"
        )

    # --- supported question: call succeeds when error_code expected ---

    def test_runner_marks_fail_when_expected_error_but_question_succeeds(self) -> None:
        """
        FAILS: module missing.
        Question is phrased to pass inspection but benchmark expects UNSUPPORTED_QUESTION.
        """
        result = self._run([
            {
                "id": "q-should-error",
                # This phrasing passes the gate — no unsupported tokens
                "question": "What is the architecture of the queue component?",
                "type": "documented-decision",
                "supported": False,
                "expected": {"error_code": "UNSUPPORTED_QUESTION"},
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertFalse(
            q_result["passed"],
            "Runner must mark fail when question succeeds but error_code was expected"
        )

    # --- supported question: must_not_be_unknown ---

    def test_runner_passes_when_documented_decision_found(self) -> None:
        """
        FAILS: module missing.
        ADR 001 contains explicit rationale; the question should not produce unknown.
        """
        result = self._run([
            {
                "id": "q-documented",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                    "likely_evidence": ["docs/adr/001-queue.md"],
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertTrue(
            q_result["passed"],
            f"Expected pass: ADR with rationale should satisfy must_not_be_unknown. Got: {q_result}"
        )

    def test_runner_fails_when_documented_rationale_absent(self) -> None:
        """
        FAILS: module missing.
        Question about Redis has no ADR; must_not_be_unknown should be violated.
        """
        result = self._run([
            {
                "id": "q-undocumented",
                "question": "Why does myservice use Redis for caching?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertFalse(
            q_result["passed"],
            "Expected fail: Redis rationale is absent; must_not_be_unknown should be violated"
        )

    # --- supported question: must_report_unknown_rationale ---

    def test_runner_passes_when_unknown_rationale_is_expected(self) -> None:
        """
        FAILS: module missing.
        Benchmark explicitly expects unknown; runner must accept that outcome.
        """
        result = self._run([
            {
                "id": "q-honest-unknown",
                "question": "Why does myservice use Redis for caching?",
                "type": "honest-unknown",
                "expected": {
                    "must_report_unknown_rationale": True,
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertTrue(
            q_result["passed"],
            f"Expected pass: unknown rationale satisfies must_report_unknown_rationale. Got: {q_result}"
        )

    # --- likely_evidence check ---

    def test_runner_fails_when_likely_evidence_not_cited(self) -> None:
        """
        FAILS: module missing.
        Benchmark declares likely_evidence that does not match any cited path.
        """
        result = self._run([
            {
                "id": "q-wrong-evidence",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                    "likely_evidence": ["docs/nonexistent/decision.md"],
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertFalse(
            q_result["passed"],
            "Runner must fail when no likely_evidence path appears in cited evidence"
        )

    def test_runner_passes_when_at_least_one_evidence_path_cited(self) -> None:
        """
        FAILS: module missing.
        Only one of multiple likely_evidence paths needs to appear.
        """
        result = self._run([
            {
                "id": "q-partial-evidence",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                    "likely_evidence": [
                        "docs/adr/001-queue.md",
                        "docs/nonexistent/other.md",
                    ],
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertTrue(
            q_result["passed"],
            f"Runner should pass when at least one likely_evidence path is cited. Got: {q_result}"
        )

    # --- result structure ---

    def test_result_is_json_serialisable(self) -> None:
        """FAILS: module missing. run_benchmark must return JSON-serialisable output."""
        result = self._run([
            {
                "id": "q-serial",
                "question": "What is the architecture of the queue component?",
                "type": "architecture-decision",
                "expected": {"classification": "observed", "must_not_be_unknown": True},
            }
        ])
        try:
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            self.fail(f"run_benchmark result is not JSON-serialisable: {exc}")

    def test_result_has_summary_with_pass_fail_counts(self) -> None:
        """FAILS: module missing. Result must include summary.total/passed/failed/skipped."""
        result = self._run([
            {
                "id": "q-summary",
                "question": "What is the architecture of the queue component?",
                "type": "architecture-decision",
                "expected": {"classification": "observed", "must_not_be_unknown": True},
            }
        ])
        self.assertIn("summary", result, "Result must include 'summary'")
        for field in ("total", "passed", "failed", "skipped"):
            self.assertIn(
                field, result["summary"],
                f"Result summary must include '{field}'"
            )

    def test_result_has_per_question_pass_status(self) -> None:
        """FAILS: module missing. Each question result must have 'passed' bool."""
        result = self._run([
            {
                "id": "q-per-q",
                "question": "What is the architecture of the queue component?",
                "type": "architecture-decision",
                "expected": {"classification": "observed", "must_not_be_unknown": True},
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertIn("passed", q_result, "Question result must include 'passed'")
        self.assertIsInstance(q_result["passed"], bool)

    def test_result_question_includes_cited_paths(self) -> None:
        """FAILS: module missing. Question result must expose cited_paths for debugging."""
        result = self._run([
            {
                "id": "q-paths",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                    "likely_evidence": ["docs/adr/001-queue.md"],
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        self.assertIn(
            "cited_paths", q_result,
            "Question result must include 'cited_paths' for evidence traceability"
        )
        self.assertIsInstance(q_result["cited_paths"], list)

    def test_failed_question_includes_failure_reason(self) -> None:
        """FAILS: module missing. Failed questions must explain why."""
        result = self._run([
            {
                "id": "q-reason",
                # Redis rationale absent; must_not_be_unknown will be violated
                "question": "Why does myservice use Redis for caching?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                },
            }
        ])
        q_result = result["repos"][0]["questions"][0]
        if not q_result.get("passed"):
            self.assertIsNotNone(
                q_result.get("failure_reason"),
                "Failed question result must include a non-None failure_reason"
            )

    def test_summary_counts_match_question_results(self) -> None:
        """FAILS: module missing. summary.passed + summary.failed + summary.skipped == summary.total."""
        result = self._run([
            {
                "id": "q-count1",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                    "likely_evidence": ["docs/adr/001-queue.md"],
                },
            },
            {
                "id": "q-count2",
                "question": "What is the impact of changing the queue?",
                "type": "change-impact",
                "supported": False,
                "expected": {"error_code": "UNSUPPORTED_QUESTION"},
            },
        ])
        s = result["summary"]
        self.assertEqual(
            s["passed"] + s["failed"] + s["skipped"],
            s["total"],
            f"summary counts do not add up: {s}"
        )

    def test_run_benchmark_accepts_path_input(self) -> None:
        """FAILS: module missing. run_benchmark must also accept a Path to a JSON file."""
        bm = _import_runner()
        bench = self._minimal_benchmark([
            {
                "id": "q-path",
                "question": "Why does myservice use an in-process queue?",
                "type": "documented-decision",
                "expected": {
                    "classification": "observed",
                    "must_not_be_unknown": True,
                },
            }
        ])
        bench_file = self.root / "bench.json"
        bench_file.write_text(json.dumps(bench), encoding="utf-8")
        result = bm.run_benchmark(bench_file, protected_root=self.protected_root)
        self.assertIn("repos", result)


# ---------------------------------------------------------------------------
# 4. CLI entry point — all FAIL until jarvis-benchmark is wired up
# ---------------------------------------------------------------------------

class BenchmarkCLITests(unittest.TestCase):
    """
    Proves that the jarvis-benchmark CLI entry point is not yet registered.
    Tests are expected to FAIL.
    """

    def test_benchmark_module_runnable_with_python_m(self) -> None:
        """
        FAILS: jarvis_engineering.benchmark does not exist.
        `python -m jarvis_engineering.benchmark --help` must exit 0.
        """
        result = subprocess.run(
            [sys.executable, "-m", "jarvis_engineering.benchmark", "--help"],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertEqual(
            result.returncode, 0,
            f"Expected exit 0 from --help, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

    def test_cli_help_mentions_benchmark(self) -> None:
        """FAILS: no module, so no help output."""
        result = subprocess.run(
            [sys.executable, "-m", "jarvis_engineering.benchmark", "--help"],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertIn(
            "benchmark",
            result.stdout.lower(),
            "jarvis-benchmark --help output must mention 'benchmark'"
        )

    def test_cli_with_missing_benchmark_file_exits_nonzero(self) -> None:
        """
        FAILS: no module.
        Passing a non-existent file should exit non-zero with a clear error message.
        """
        result = subprocess.run(
            [
                sys.executable, "-m", "jarvis_engineering.benchmark",
                "--benchmark", "/tmp/does_not_exist.json",
            ],
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertNotEqual(
            result.returncode, 0,
            "CLI must exit non-zero when benchmark file is missing"
        )

    def test_cli_output_is_valid_json(self) -> None:
        """
        FAILS: no module.
        CLI must write valid JSON to stdout when given a valid benchmark file.
        """
        temp = tempfile.mkdtemp()
        root = Path(temp)
        remote = "https://github.com/example/testsvc"
        _make_committed_repo(
            root, "testsvc", remote,
            {
                "README.md": "# Test Service\n",
                "docs/adr/001-queue.md": BenchmarkRunnerUnitTests.ADR_BODY,
            },
        )
        bench = {
            "description": "cli test",
            "repositories_root": str(root),
            "repos": [
                {
                    "slug": "example/testsvc",
                    "github_url": remote,
                    "checkout": "testsvc",
                    "questions": [
                        {
                            "id": "q-cli",
                            "question": "What is the impact of changing the queue?",
                            "type": "change-impact",
                            "supported": False,
                            "expected": {"error_code": "UNSUPPORTED_QUESTION"},
                        }
                    ],
                }
            ],
        }
        bench_file = root / "bench.json"
        bench_file.write_text(json.dumps(bench), encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "jarvis_engineering.benchmark",
                    "--benchmark", str(bench_file),
                    "--repositories-root", str(root),
                ],
                capture_output=True,
                text=True,
                env=_subprocess_env(),
            )
            self.assertEqual(
                result.returncode, 0,
                f"CLI exited {result.returncode}. stderr: {result.stderr}"
            )
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                self.fail(f"CLI stdout is not valid JSON: {exc}\nstdout: {result.stdout[:500]}")
            self.assertIn("repos", parsed)
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_pyproject_registers_jarvis_benchmark_entry_point(self) -> None:
        """
        FAILS: pyproject.toml does not register jarvis-benchmark.
        The entry point must be wired up so `jarvis-benchmark` is available
        after `pip install -e .`.
        """
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn(
            "jarvis-benchmark",
            content,
            "pyproject.toml must register a [project.scripts] entry for jarvis-benchmark"
        )


# ---------------------------------------------------------------------------
# 5. Integration — real repos, skipped when checkout is absent
# ---------------------------------------------------------------------------

class LargeRepoBenchmarkIntegrationTests(unittest.TestCase):
    """
    Runs the benchmark runner against the real public-repo checkouts.
    Each test is skipped when the checkout is absent.
    All tests FAIL until jarvis_engineering.benchmark is implemented.
    """

    PROTECTED_ROOT = PROJECT_ROOT.parent

    def _run_repo(self, slug: str) -> dict:
        """Run the benchmark for a single repo from large_repos.json."""
        bm = _import_runner()
        data = _load_benchmark()
        repo_entry = next((r for r in data["repos"] if r["slug"] == slug), None)
        self.assertIsNotNone(repo_entry, f"No repo with slug {slug!r} in large_repos.json")
        bench = {
            "description": data.get("description", ""),
            "repositories_root": str(REPOS_ROOT),
            "repos": [repo_entry],
        }
        return bm.run_benchmark(bench, protected_root=self.PROTECTED_ROOT)

    def _require_checkout(self, slug: str) -> None:
        repo_name = slug.split("/")[1]
        checkout = REPOS_ROOT / repo_name
        if not checkout.exists():
            self.skipTest(f"Checkout {checkout} not found — clone first")

    # --- flask ---

    def test_flask_all_negative_cases_refused(self) -> None:
        """
        FAILS: module missing. Skipped if flask checkout absent.
        All UNSUPPORTED_QUESTION entries in the flask section must be refused.
        """
        self._require_checkout("pallets/flask")
        result = self._run_repo("pallets/flask")
        data = _load_benchmark()
        flask_entry = next(r for r in data["repos"] if r["slug"] == "pallets/flask")
        negative_ids = {
            q["id"] for q in flask_entry["questions"]
            if q.get("supported") is False
        }
        for repo_result in result["repos"]:
            for q_result in repo_result["questions"]:
                if q_result["id"] in negative_ids:
                    self.assertTrue(
                        q_result["passed"],
                        f"Negative case {q_result['id']!r} was not correctly refused: {q_result}"
                    )

    def test_flask_explicit_app_object_finds_evidence(self) -> None:
        """
        FAILS: module missing. Skipped if flask checkout absent.
        design.rst contains documented rationale for explicit app object.
        """
        self._require_checkout("pallets/flask")
        result = self._run_repo("pallets/flask")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "flask-explicit-app-object"),
            None,
        )
        self.assertIsNotNone(q_result, "flask-explicit-app-object not found in result")
        self.assertTrue(
            q_result["passed"],
            f"flask-explicit-app-object expected pass, got: {q_result}"
        )

    def test_flask_blueprints_finds_evidence(self) -> None:
        """FAILS: module missing. Skipped if flask checkout absent."""
        self._require_checkout("pallets/flask")
        result = self._run_repo("pallets/flask")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "flask-blueprints"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(q_result["passed"], f"flask-blueprints failed: {q_result}")

    # --- backstage ---

    def test_backstage_all_negative_cases_refused(self) -> None:
        """FAILS: module missing. Skipped if backstage checkout absent."""
        self._require_checkout("backstage/backstage")
        result = self._run_repo("backstage/backstage")
        data = _load_benchmark()
        entry = next(r for r in data["repos"] if r["slug"] == "backstage/backstage")
        negative_ids = {q["id"] for q in entry["questions"] if q.get("supported") is False}
        for repo_result in result["repos"]:
            for q_result in repo_result["questions"]:
                if q_result["id"] in negative_ids:
                    self.assertTrue(
                        q_result["passed"],
                        f"Negative case {q_result['id']!r} not refused: {q_result}"
                    )

    def test_backstage_avoid_default_exports_finds_adr(self) -> None:
        """FAILS: module missing. Skipped if backstage checkout absent."""
        self._require_checkout("backstage/backstage")
        result = self._run_repo("backstage/backstage")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "backstage-avoid-default-exports"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(
            q_result["passed"],
            f"backstage-avoid-default-exports failed: {q_result}"
        )

    def test_backstage_fetch_evolution_finds_both_adrs(self) -> None:
        """
        FAILS: module missing. Skipped if backstage checkout absent.
        The decision-evolution question should surface both adr013 and adr014.
        """
        self._require_checkout("backstage/backstage")
        result = self._run_repo("backstage/backstage")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "backstage-fetch-evolution"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(
            q_result["passed"],
            f"backstage-fetch-evolution failed: {q_result}"
        )

    # --- opentelemetry-specification ---

    def test_otel_all_negative_cases_refused(self) -> None:
        """FAILS: module missing. Skipped if opentelemetry-specification checkout absent."""
        self._require_checkout("open-telemetry/opentelemetry-specification")
        result = self._run_repo("open-telemetry/opentelemetry-specification")
        data = _load_benchmark()
        entry = next(
            r for r in data["repos"]
            if r["slug"] == "open-telemetry/opentelemetry-specification"
        )
        negative_ids = {q["id"] for q in entry["questions"] if q.get("supported") is False}
        for repo_result in result["repos"]:
            for q_result in repo_result["questions"]:
                if q_result["id"] in negative_ids:
                    self.assertTrue(
                        q_result["passed"],
                        f"Negative case {q_result['id']!r} not refused: {q_result}"
                    )

    def test_otel_separate_context_propagation_finds_otep(self) -> None:
        """FAILS: module missing. Skipped if opentelemetry-specification checkout absent."""
        self._require_checkout("open-telemetry/opentelemetry-specification")
        result = self._run_repo("open-telemetry/opentelemetry-specification")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "otel-separate-context-propagation"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(
            q_result["passed"],
            f"otel-separate-context-propagation failed: {q_result}"
        )

    # --- zalando restful-api-guidelines ---

    def test_zalando_all_negative_cases_refused(self) -> None:
        """FAILS: module missing. Skipped if restful-api-guidelines checkout absent."""
        self._require_checkout("zalando/restful-api-guidelines")
        result = self._run_repo("zalando/restful-api-guidelines")
        data = _load_benchmark()
        entry = next(
            r for r in data["repos"] if r["slug"] == "zalando/restful-api-guidelines"
        )
        negative_ids = {q["id"] for q in entry["questions"] if q.get("supported") is False}
        for repo_result in result["repos"]:
            for q_result in repo_result["questions"]:
                if q_result["id"] in negative_ids:
                    self.assertTrue(
                        q_result["passed"],
                        f"Negative case {q_result['id']!r} not refused: {q_result}"
                    )

    def test_zalando_cursor_pagination_finds_rationale(self) -> None:
        """FAILS: module missing. Skipped if restful-api-guidelines checkout absent."""
        self._require_checkout("zalando/restful-api-guidelines")
        result = self._run_repo("zalando/restful-api-guidelines")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "zalando-cursor-pagination"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(
            q_result["passed"],
            f"zalando-cursor-pagination failed: {q_result}"
        )

    # --- govuk-design-system ---

    def test_govuk_all_negative_cases_refused(self) -> None:
        """FAILS: module missing. Skipped if govuk-design-system checkout absent."""
        self._require_checkout("alphagov/govuk-design-system")
        result = self._run_repo("alphagov/govuk-design-system")
        data = _load_benchmark()
        entry = next(
            r for r in data["repos"] if r["slug"] == "alphagov/govuk-design-system"
        )
        negative_ids = {q["id"] for q in entry["questions"] if q.get("supported") is False}
        for repo_result in result["repos"]:
            for q_result in repo_result["questions"]:
                if q_result["id"] in negative_ids:
                    self.assertTrue(
                        q_result["passed"],
                        f"Negative case {q_result['id']!r} not refused: {q_result}"
                    )

    def test_govuk_colour_palette_returns_honest_unknown(self) -> None:
        """
        FAILS: module missing. Skipped if govuk-design-system checkout absent.
        Colour-palette rationale lives in govuk-frontend, not this repo.
        v1 must return unknown, not fabricate an answer.
        """
        self._require_checkout("alphagov/govuk-design-system")
        result = self._run_repo("alphagov/govuk-design-system")
        q_result = next(
            (q for r in result["repos"] for q in r["questions"]
             if q["id"] == "govuk-color-palette-unknown"),
            None,
        )
        self.assertIsNotNone(q_result)
        self.assertTrue(
            q_result["passed"],
            f"govuk-color-palette-unknown: expected pass for honest-unknown, got: {q_result}"
        )

    # --- cross-repo summary ---

    def test_full_benchmark_result_has_correct_total_count(self) -> None:
        """
        FAILS: module missing. Skipped if any repo is missing.
        Runs the complete large_repos.json benchmark and checks total question count.
        """
        data = _load_benchmark()
        for repo in data["repos"]:
            repo_name = repo["slug"].split("/")[1]
            checkout = REPOS_ROOT / repo_name
            if not checkout.exists():
                self.skipTest(
                    f"Checkout {checkout} not found — run all repo clones first"
                )
        bm = _import_runner()
        result = bm.run_benchmark(
            BENCHMARK_PATH,
            protected_root=self.PROTECTED_ROOT,
        )
        expected_total = sum(len(r["questions"]) for r in data["repos"])
        self.assertEqual(
            result["summary"]["total"],
            expected_total,
            f"Expected {expected_total} total questions, got {result['summary']['total']}"
        )


if __name__ == "__main__":
    unittest.main()
