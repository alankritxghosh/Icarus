"""
Day 2 safety validation pass for JARVIS Engineering Intelligence.

Covers six targeted safety checklist areas to verify the properties are solid
after the v1 repair. Where a test fails it proves a remaining gap — it does not
indicate a test-writing error.

Areas:
  1. Bad paths — non-existent checkout, file-not-directory, missing root, .jsonl in paths.
  2. Personal brain paths — checkout under protected_root, checkout == protected_root,
     and no protected_root (fail-closed).
  3. Question sanitisation — .jsonl / brain/ / ../ in the question text itself.
  4. GitHub URL / local-checkout mismatch — REMOTE_MISMATCH and no-remote warning.
  5. Unsupported impact/dependency phrasings — consumer-discovery and change-impact
     surface forms that the unsupported-intent gate must catch.
  6. Real public repo inspection — skipped when no local clone is available.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

import sys
sys.path.insert(0, str(SRC_ROOT))

from jarvis_engineering.contracts import ErrorCode, InspectionError
from jarvis_engineering.inspector import inspect_repository

_GITHUB_URL = "https://github.com/example/test-repo"
_GITHUB_REMOTE = "https://github.com/example/test-repo.git"


# ---------------------------------------------------------------------------
# Shared deterministic helpers (same pattern as test_safety_honesty.py)
# ---------------------------------------------------------------------------

def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_repo(root: Path, name: str, remote: str | None = None) -> Path:
    """Initialise a minimal git repo under root/name; optionally set origin."""
    checkout = root / name
    checkout.mkdir(parents=True)
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "tests@example.com")
    _git(checkout, "config", "user.name", "JARVIS Tests")
    if remote is not None:
        _git(checkout, "remote", "add", "origin", remote)
    return checkout


def _commit(checkout: Path, files: dict[str, str]) -> None:
    """Write files into the checkout and create a single commit."""
    for path_str, content in files.items():
        dest = checkout / path_str
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "fixture")


# ---------------------------------------------------------------------------
# Area 1: Bad paths
# ---------------------------------------------------------------------------

class BadPathTests(unittest.TestCase):
    """
    Prove that malformed path arguments are rejected with the correct error codes
    before any Git or evidence work is attempted.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_checkout_path_does_not_exist(self) -> None:
        """A checkout path that does not exist on disk must raise CHECKOUT_NOT_FOUND."""
        nonexistent = str(self.root / "no_such_dir")
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                nonexistent,
                str(self.root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.CHECKOUT_NOT_FOUND)

    def test_checkout_is_a_file_not_directory(self) -> None:
        """
        A checkout path that resolves to a regular file (not a directory) must
        raise CHECKOUT_NOT_FOUND. The file exists, so resolve(strict=True) succeeds
        but is_dir() returns False.
        """
        file_path = self.root / "repo.txt"
        file_path.write_text("I am a file, not a directory\n", encoding="utf-8")
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                str(file_path),
                str(self.root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.CHECKOUT_NOT_FOUND)

    def test_repositories_root_does_not_exist(self) -> None:
        """A repositories_root that does not exist must raise INVALID_REPOSITORIES_ROOT."""
        nonexistent_root = str(self.root / "no_such_root")
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                "sample",
                nonexistent_root,
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_REPOSITORIES_ROOT)

    def test_jsonl_in_repositories_root_arg(self) -> None:
        """
        A repositories_root path containing .jsonl in any path component must raise
        JSONL_ACCESS_DENIED. The check fires before path resolution, so the path
        does not need to exist.
        """
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                "sample",
                "/some/data.jsonl/repos",
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.JSONL_ACCESS_DENIED)

    def test_jsonl_in_checkout_arg(self) -> None:
        """
        A checkout path containing .jsonl in any path component must raise
        JSONL_ACCESS_DENIED. The root is valid; the .jsonl check on the checkout
        fires before resolve(strict=True), so the checkout path need not exist.
        """
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                "/some/observations.jsonl/sample",
                str(self.root),   # valid, existing root
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.JSONL_ACCESS_DENIED)


# ---------------------------------------------------------------------------
# Area 2: Personal brain paths
# ---------------------------------------------------------------------------

class PersonalBrainPathTests(unittest.TestCase):
    """
    Prove that personal-root protection is enforced at three boundary conditions:
    checkout inside protected_root, checkout equal to protected_root, and
    protected_root omitted entirely (fail-closed).
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_checkout_under_protected_root_is_blocked(self) -> None:
        """
        A checkout whose resolved path is INSIDE protected_root must raise
        PROTECTED_ROOT_ACCESS.

        Layout:
          self.root/               ← protected_root
            repos/                 ← repositories_root
              sample/              ← checkout (inside protected_root)
        """
        repos_dir = self.root / "repos"
        repos_dir.mkdir()
        checkout = _make_repo(repos_dir, "sample", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Protected sample\n"})

        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                str(checkout),
                str(repos_dir),
                "What is the architecture?",
                protected_root=self.root,   # ancestor of checkout
            )
        self.assertEqual(caught.exception.code, ErrorCode.PROTECTED_ROOT_ACCESS)

    def test_checkout_equals_protected_root_boundary(self) -> None:
        """
        A checkout that IS EXACTLY the protected_root (resolved equality boundary)
        must raise PROTECTED_ROOT_ACCESS. The code uses `resolved == protected` to
        cover this case.
        """
        checkout = _make_repo(self.root, "sample", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Boundary sample\n"})

        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                str(checkout),
                str(self.root),        # root contains checkout — valid containment
                "What is the architecture?",
                protected_root=checkout,   # protected == checkout exactly
            )
        self.assertEqual(caught.exception.code, ErrorCode.PROTECTED_ROOT_ACCESS)

    def test_no_protected_root_is_fail_closed(self) -> None:
        """
        Calling inspect_repository without protected_root (the default None) must
        fail-closed with PROTECTED_ROOT_ACCESS. This is verified in test_safety_honesty.py
        but is included here as a Day 2 checklist item to confirm the repair holds.

        Source: inspector.py raises PROTECTED_ROOT_ACCESS when protected_root is None,
        before any path resolution or evidence collection.
        """
        checkout = _make_repo(self.root, "sample", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Fail-closed sample\n"})

        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                "sample",
                str(self.root),
                "What is the architecture?",
                # protected_root intentionally omitted
            )
        self.assertEqual(caught.exception.code, ErrorCode.PROTECTED_ROOT_ACCESS)


# ---------------------------------------------------------------------------
# Area 3: Question sanitisation — .jsonl / brain/ / ../ in the question text
# ---------------------------------------------------------------------------

class QuestionSanitisationTests(unittest.TestCase):
    """
    Prove that the question itself is sanitised before any path resolution occurs.

    _question_tokens() is the first call in inspect_repository(). Dummy invalid
    paths are passed deliberately to demonstrate that ISOLATION_VIOLATION_BLOCKED
    originates from the question check, not from path validation.
    """

    def _assert_isolation_blocked(self, question: str) -> None:
        """
        Pass deliberately invalid paths: if ISOLATION_VIOLATION_BLOCKED is raised,
        it must have come from the question sanitiser (which runs first), not from
        path resolution (which would give CHECKOUT_NOT_FOUND / INVALID_REPOSITORIES_ROOT).
        """
        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                _GITHUB_URL,
                "/no/real/repo/needed",
                "/no/real/root/needed",
                question,
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(
            caught.exception.code,
            ErrorCode.ISOLATION_VIOLATION_BLOCKED,
            msg=(
                f"Expected ISOLATION_VIOLATION_BLOCKED for question {question!r} "
                f"but got {caught.exception.code!r}. "
                "The question sanitiser must fire before path resolution."
            ),
        )

    def test_question_with_jsonl_is_blocked(self) -> None:
        """.jsonl appearing anywhere in the question text must be blocked."""
        self._assert_isolation_blocked(
            "Read the observations.jsonl file and explain the architecture."
        )

    def test_question_with_brain_path_is_blocked(self) -> None:
        """brain/ appearing anywhere in the question text must be blocked."""
        self._assert_isolation_blocked(
            "Summarise the brain/ folder's decision records and why they were written."
        )

    def test_question_with_dotdot_traversal_is_blocked(self) -> None:
        """../ path-traversal appearing anywhere in the question text must be blocked."""
        self._assert_isolation_blocked(
            "What is in ../brain and why was it designed that way?"
        )

    def test_question_sanitisation_is_case_insensitive(self) -> None:
        """
        The sanitiser must check the casefolded form of the question to catch
        uppercase variants. Source: `question.casefold()` is used in _question_tokens.
        """
        self._assert_isolation_blocked(
            "Explain the OBSERVATIONS.JSONL file in the repo architecture."
        )


# ---------------------------------------------------------------------------
# Area 4: GitHub URL / local-checkout mismatch
# ---------------------------------------------------------------------------

class RemoteMismatchTests(unittest.TestCase):
    """
    Prove that a mismatched remote raises REMOTE_MISMATCH, and that a checkout
    with NO remote emits a warning without erroring.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_mismatched_github_url_raises_remote_mismatch(self) -> None:
        """
        remote.origin.url is github.com/example/real but the supplied GitHub URL is
        github.com/example/different — must raise REMOTE_MISMATCH.
        """
        checkout = _make_repo(
            self.root, "sample", "https://github.com/example/real.git"
        )
        _commit(checkout, {"README.md": "# Real repo\n"})

        with self.assertRaises(InspectionError) as caught:
            inspect_repository(
                "https://github.com/example/different",   # mismatched URL
                "sample",
                str(self.root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )
        self.assertEqual(caught.exception.code, ErrorCode.REMOTE_MISMATCH)

    def test_no_remote_origin_emits_warning_not_error(self) -> None:
        """
        A checkout with no remote.origin.url must NOT raise an error. It must
        return a successful report with a warning about unverified identity.

        Source: inspector.py — when read_origin() returns None, a warning is
        appended and inspection continues normally.
        """
        checkout = _make_repo(self.root, "no_remote", remote=None)  # no origin
        _commit(checkout, {"README.md": "# No remote\nService architecture.\n"})

        report = inspect_repository(
            _GITHUB_URL,
            "no_remote",
            str(self.root),
            "What is the architecture?",
            protected_root=PROJECT_ROOT.parent,
        )

        self.assertTrue(
            report["ok"],
            msg="A checkout with no remote must succeed and return ok=True.",
        )
        warning_text = " ".join(report["warnings"]).casefold()
        self.assertIn(
            "remote.origin.url",
            warning_text,
            msg=(
                "Expected a warning mentioning 'remote.origin.url' for a checkout "
                "with no remote. Got warnings: " + repr(report["warnings"])
            ),
        )


# ---------------------------------------------------------------------------
# Area 5: Unsupported impact/dependency phrasings
# ---------------------------------------------------------------------------

class UnsupportedImpactQuestionTests(unittest.TestCase):
    """
    Prove whether the source correctly refuses consumer-discovery and
    change-impact phrasings.

    The five questions are the S1 honesty risk the architect flagged: they are
    semantically dependency-tracing or change-impact queries and use surface
    phrasings like 'uses', 'relies on', 'breaks when', 'consumes', and 'calls'.
    """

    REMOTE = "https://github.com/example/svc.git"
    URL = "https://github.com/example/svc"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = _make_repo(self.root, "sample", self.REMOTE)
        _commit(self.checkout, {
            "README.md": (
                "# Service\n\nThis service handles payments, auth, and orders.\n"
            ),
            "src/service.py": (
                "class PaymentService:\n    pass\n\n"
                "class AuthModule:\n    pass\n\n"
                "class OrderService:\n    pass\n"
            ),
        })

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _inspect(self, question: str) -> dict:
        return inspect_repository(
            self.URL,
            "sample",
            str(self.root),
            question,
            protected_root=PROJECT_ROOT.parent,
        )

    def _assert_unsupported(self, question: str) -> None:
        """Assert that an impact/consumer question raises UNSUPPORTED_QUESTION."""
        with self.assertRaises(InspectionError) as caught:
            self._inspect(question)
        self.assertEqual(
            caught.exception.code,
            ErrorCode.UNSUPPORTED_QUESTION,
            msg=(
                f"Expected UNSUPPORTED_QUESTION for dependency/consumer question "
                f"{question!r} but got {caught.exception.code!r}. "
                "The unsupported-intent gate does not catch this phrasing."
            ),
        )

    def test_what_uses_payment_service_is_unsupported(self) -> None:
        """
        'What uses X?' is a dependency-consumer question; must be UNSUPPORTED_QUESTION.

        This must be refused because the product cannot trace consumers.
        """
        self._assert_unsupported("What uses the payment service?")

    def test_what_relies_on_is_unsupported(self) -> None:
        """
        'What relies on X?' is a dependency question; must be UNSUPPORTED_QUESTION.

        This must be refused because the product cannot trace dependencies.
        """
        self._assert_unsupported("What relies on the auth module?")

    def test_what_breaks_when_delete_is_unsupported(self) -> None:
        """
        'What breaks when I delete X?' is a change-impact question;
        must be UNSUPPORTED_QUESTION.

        This must be refused because the product cannot do change-impact analysis.
        """
        self._assert_unsupported("What breaks when I delete the cache layer?")

    def test_what_consumes_is_unsupported(self) -> None:
        """
        'What consumes X?' is a dependency-consumer question; must be UNSUPPORTED_QUESTION.

        This must be refused because the product cannot trace consumers.
        """
        self._assert_unsupported("What consumes the checkout API?")

    def test_what_calls_is_unsupported(self) -> None:
        """
        'What calls X?' is a caller-graph / dependency-tracing question;
        must be UNSUPPORTED_QUESTION.

        This must be refused because the product cannot build a caller graph.
        """
        self._assert_unsupported("What calls the order service?")

    def test_valid_architecture_question_does_not_raise(self) -> None:
        """
        Negative control: a valid documented-decision / architecture question on the
        same fixture must NOT raise UNSUPPORTED_QUESTION and must return a report.
        """
        report = self._inspect(
            "Why did the team choose this architecture for the service?"
        )
        self.assertTrue(
            report["ok"],
            msg="A valid why/architecture question must return ok=True.",
        )


# ---------------------------------------------------------------------------
# Area 5b: Unsupported question regression tests (new phrasings)
# ---------------------------------------------------------------------------

class UnsupportedQuestionRegressionTests(unittest.TestCase):
    """
    Regression suite for question phrasings that are semantically equivalent to
    the dependency-tracing and change-impact queries that the unsupported-intent
    gate must refuse.

    For each must-be-refused test the EXPECTED outcome is UNSUPPORTED_QUESTION.
    Tests that FAIL prove the gate has a gap (the question slips through and the
    product would return misleading output instead of an honest refusal).

    For each must-be-allowed test the EXPECTED outcome is ok=True. Tests that
    FAIL would indicate over-blocking of legitimate documented-decision questions.

    The fixture only needs to exist as a committed git repo. Question-level
    refusal fires in _question_tokens() before any evidence collection, so the
    fixture content does not affect the outcome of unsupported-question tests.
    """

    REMOTE = "https://github.com/example/svc-regression.git"
    URL = "https://github.com/example/svc-regression"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.checkout = _make_repo(self.root, "sample", self.REMOTE)
        _commit(self.checkout, {
            "README.md": (
                "# Service\n\n"
                "This service handles authentication, payments, and order fulfilment.\n"
            ),
            "src/main.py": (
                "# Main entry point\n"
                "class AuthModule:\n    pass\n\n"
                "class PaymentService:\n    pass\n\n"
                "class OrderService:\n    pass\n"
            ),
        })

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _inspect(self, question: str) -> dict:
        return inspect_repository(
            self.URL,
            "sample",
            str(self.root),
            question,
            protected_root=PROJECT_ROOT.parent,
        )

    def _assert_unsupported(self, question: str) -> None:
        """Assert that the question is refused with UNSUPPORTED_QUESTION."""
        with self.assertRaises(InspectionError) as caught:
            self._inspect(question)
        self.assertEqual(
            caught.exception.code,
            ErrorCode.UNSUPPORTED_QUESTION,
            msg=(
                f"Expected UNSUPPORTED_QUESTION for consumer/dependency question "
                f"{question!r} but got {caught.exception.code!r}. "
                "The unsupported-intent gate does not match this phrasing."
            ),
        )

    # ------------------------------------------------------------------
    # Must-be-refused: questions already caught by the unsupported-intent gate.
    # These tests document confirmed behaviour and must keep passing.
    # ------------------------------------------------------------------

    def test_who_uses_payment_service_is_refused(self) -> None:
        """
        'Who uses X?' is a consumer-discovery question.

        The unsupported-intent gate catches this phrasing and must keep doing so.
        """
        self._assert_unsupported("Who uses the payment service?")

    def test_which_module_calls_order_service_is_refused(self) -> None:
        """
        'Which module calls X?' is a caller-graph question.

        The unsupported-intent gate catches this phrasing and must keep doing so.
        """
        self._assert_unsupported("Which module calls the order service?")

    def test_what_code_consumes_checkout_events_is_refused(self) -> None:
        """
        'What code consumes X?' is a consumer-discovery question.

        The unsupported-intent gate catches this phrasing and must keep doing so.
        """
        self._assert_unsupported("What code consumes checkout events?")

    # ------------------------------------------------------------------
    # Must-be-refused: previously missed forms. These must remain covered.
    # ------------------------------------------------------------------

    def test_what_breaks_if_remove_cache_is_refused(self) -> None:
        """
        'What breaks if we remove X?' is a change-impact question and must be
        refused with UNSUPPORTED_QUESTION.

        Expected: UNSUPPORTED_QUESTION.
        """
        self._assert_unsupported("What breaks if we remove the cache layer?")

    def test_what_relies_upon_auth_module_is_refused(self) -> None:
        """
        'What relies upon X?' is a reverse-dependency question and must be
        refused with UNSUPPORTED_QUESTION.

        Expected: UNSUPPORTED_QUESTION.
        """
        self._assert_unsupported("What relies upon the auth module?")

    def test_what_depends_upon_redis_is_refused(self) -> None:
        """
        'What depends upon X?' is a dependency-tracing question and must be
        refused with UNSUPPORTED_QUESTION.

        Expected: UNSUPPORTED_QUESTION.
        """
        self._assert_unsupported("What depends upon Redis?")

    # ------------------------------------------------------------------
    # Must-be-allowed: valid documented-decision questions that must NOT
    # be blocked. These test over-blocking regressions.
    # ------------------------------------------------------------------

    def test_why_choose_architecture_is_allowed(self) -> None:
        """
        'Why did the team choose this architecture?' is a valid documented-decision
        question and must return ok=True without raising.

        This must not be over-blocked by the unsupported-intent gate.
        """
        report = self._inspect("Why did the team choose this architecture?")
        self.assertTrue(
            report["ok"],
            msg=(
                "Valid documented-decision question 'Why did the team choose this "
                "architecture?' must return ok=True. Over-blocking would be a regression."
            ),
        )

    def test_why_was_redis_introduced_is_allowed(self) -> None:
        """
        'Why was Redis introduced?' is a valid rationale question and must
        return ok=True without raising.

        The term 'Redis' appears in fixture content; the term 'introduced'
        carries no unsupported semantics.
        """
        report = self._inspect("Why was Redis introduced?")
        self.assertTrue(
            report["ok"],
            msg=(
                "Valid rationale question 'Why was Redis introduced?' must return "
                "ok=True. Over-blocking would be a regression."
            ),
        )

    def test_rationale_for_event_bus_is_allowed(self) -> None:
        """
        'What is the rationale for the event bus?' is a documented-decision
        question and must return ok=True without raising.

        'rationale' is in _QUESTION_TERMS; no term in the question should trigger
        the unsupported-intent gate.
        """
        report = self._inspect("What is the rationale for the event bus?")
        self.assertTrue(
            report["ok"],
            msg=(
                "Valid rationale question 'What is the rationale for the event bus?' "
                "must return ok=True. Over-blocking would be a regression."
            ),
        )

    def test_main_service_modules_is_allowed(self) -> None:
        """
        'What are the main service modules?' is a structural documentation
        question and must return ok=True without raising.

        'service' is in _QUESTION_TERMS; no term in this question should trigger
        the unsupported-intent gate.
        """
        report = self._inspect("What are the main service modules?")
        self.assertTrue(
            report["ok"],
            msg=(
                "Valid structural question 'What are the main service modules?' "
                "must return ok=True. Over-blocking would be a regression."
            ),
        )


# ---------------------------------------------------------------------------
# Area 6: One real public repo inspection
# ---------------------------------------------------------------------------

_FLASK_CLONE = Path.home() / "jarvis_test_repos" / "flask"
_FLASK_URL = "https://github.com/pallets/flask"


@unittest.skip(
    "No local public-repo clone is available. "
    "Enable this test class by running: "
    "git clone https://github.com/pallets/flask ~/jarvis_test_repos/flask"
)
class RealPublicRepoInspectionTests(unittest.TestCase):
    """
    Smoke-test inspect_repository against a real public repository clone.

    Requires a pre-existing local clone; skipped when absent so the suite
    remains self-contained and network-free. Remove the @skip decorator and
    re-run after cloning.
    """

    def setUp(self) -> None:
        # Confirm the clone is still present at test-start; skip if it vanished.
        if not _FLASK_CLONE.is_dir():
            self.skipTest(
                f"Flask clone not found at {_FLASK_CLONE}. "
                "Run: git clone https://github.com/pallets/flask ~/jarvis_test_repos/flask"
            )
        self.root = _FLASK_CLONE.parent  # ~/jarvis_test_repos/

    def test_flask_inspection_returns_ok_report(self) -> None:
        """
        inspect_repository on the Flask clone must return ok=True with a 40-hex
        HEAD SHA, a non-empty evidence list, and a JSON-serialisable payload.
        """
        import json as _json

        report = inspect_repository(
            _FLASK_URL,
            str(_FLASK_CLONE),
            str(self.root),
            "Why does Flask use a pluggable application factory pattern?",
            protected_root=PROJECT_ROOT.parent,
        )

        self.assertTrue(report["ok"], msg="Report must be ok=True for a real repo.")
        head_sha = report["repository"]["head_sha"]
        self.assertRegex(
            head_sha,
            r"^[0-9a-f]{40}$",
            msg=f"HEAD SHA must be 40 hex chars; got {head_sha!r}.",
        )
        self.assertGreater(
            len(report["evidence"]),
            0,
            msg="Evidence list must be non-empty for a real repository.",
        )
        # Confirm the entire report is JSON-serialisable (no dataclasses left unserialised)
        _json.dumps(report)


if __name__ == "__main__":
    unittest.main()
