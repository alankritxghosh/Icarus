"""
Acceptance tests for the Natural Command Layer (PLAN_NATURAL_COMMAND_LAYER.md).

12 acceptance criteria mapped to test methods:

New behavior tests (criteria 1–5): call cli.main() with the new argument surface
(question as the only required positional, optional path positional, optional
--github-url and --repositories-root).  ALL of these FAIL today because the
current parser requires github_url checkout question --repositories-root.

Re-proven safety invariants (criteria 6–12): verify existing safety contracts hold
through the new (or current) CLI surface.

Expected results before implementation:
  FAIL  test_cwd_inference_without_flags                       criterion 1 — new CLI surface
  FAIL  test_subdirectory_resolves_to_toplevel                 criterion 2 — new CLI surface
  FAIL  test_non_git_cwd_returns_json_error                    criterion 3 — returns INVALID_ARGUMENTS, not NOT_GIT_REPOSITORY
  FAIL  test_inferred_identity_adds_derived_warning            criterion 4 — new CLI surface
  FAIL  test_no_origin_without_github_url_flag_errors          criterion 5 — argparse fires before origin check
  FAIL  test_explicit_github_url_mismatch_raises_remote_mismatch  criterion 6 — --github-url flag unrecognised today
  PASS  test_protected_root_blocks_inferred_checkout           criterion 7 — uses current CLI surface + patched protected root
  PASS  test_protected_root_is_package_anchored                criterion 8 — unit test of _default_protected_root()
  FAIL  test_explicit_repositories_root_enables_checkout_outside_root_error  criterion 9 — new CLI surface
  FAIL  test_jsonl_in_inferred_path_is_blocked                 criterion 10 — new CLI surface (current parser returns INVALID_GITHUB_URL)
  PASS  test_no_new_dependencies_in_pyproject                  criterion 11 — static file check
  PASS  test_existing_suite_api_is_unchanged                   criterion 12 — calls inspect_repository directly
"""
from __future__ import annotations

import contextlib
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

from jarvis_engineering import cli
from jarvis_engineering.contracts import ErrorCode
from jarvis_engineering.inspector import inspect_repository

_GITHUB_URL = "https://github.com/example/myrepo"
_GITHUB_REMOTE = "https://github.com/example/myrepo.git"

# A protected-root value that is definitely outside every temp directory used
# in these tests, so it never triggers PROTECTED_ROOT_ACCESS accidentally.
# Path.resolve() works on non-existent paths (no strict=True); isolation.py's
# _is_within will return False for any real temp checkout vs this sentinel.
_SAFE_PROTECTED_ROOT = Path("/nonexistent_protected_root_for_tests")


# ---------------------------------------------------------------------------
# Shared helpers (same pattern as test_day2_safety.py)
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


def _call_main(
    argv: list[str],
    *,
    cwd: Path | None = None,
    protected_root: Path | None = None,
) -> tuple[int, dict]:
    """
    Call cli.main(argv), capture stdout, return (exit_code, parsed_report_dict).

    cwd:            if given, patches pathlib.Path.cwd to return this value so that
                    the new resolver's cwd-inference logic sees it.
    protected_root: if given, patches jarvis_engineering.cli._default_protected_root
                    to return this value, simulating a different protected root.

    cli.main always emits JSON to stdout (even on errors) so the returned dict
    will always be non-empty.
    """
    buf = io.StringIO()
    patches: list = [
        mock.patch("sys.stdout", buf),
        mock.patch.dict(os.environ, {"JARVIS_PROTECTED_ROOT": str(_SAFE_PROTECTED_ROOT)}),
    ]
    if cwd is not None:
        # Path.cwd is a classmethod; replacing it with a MagicMock(return_value=cwd)
        # makes any call to Path.cwd() return the supplied path.
        patches.append(mock.patch("pathlib.Path.cwd", return_value=cwd))
    if protected_root is not None:
        patches.append(
            mock.patch(
                "jarvis_engineering.cli._default_protected_root",
                return_value=protected_root,
            )
        )
    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        exit_code = cli.main(argv)
    output = buf.getvalue().strip()
    report = json.loads(output) if output else {}
    return exit_code, report


# ---------------------------------------------------------------------------
# Criteria 1–5: new cwd-inference CLI surface
# ---------------------------------------------------------------------------

class CwdInferenceTests(unittest.TestCase):
    """
    Criteria 1–5: the new CLI argument surface (question-only positional, optional
    path positional, optional --github-url and --repositories-root).

    ALL tests in this class are EXPECTED TO FAIL before implementation.

    Root cause of failure today: the current _parser() requires three positionals
    (github_url, checkout, question) plus required --repositories-root.  Calling
    with the new argv form hits argparse's error handler → InspectionError(
    INVALID_ARGUMENTS) before any git or resolver logic runs.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    # ------------------------------------------------------------------
    # Criterion 1
    # ------------------------------------------------------------------

    def test_cwd_inference_without_flags(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 1: calling cli.main with only a question (no --github-url, no
        --repositories-root, no checkout path) from inside a git checkout whose
        origin is a canonical GitHub URL must return exit_code 0 and ok=True.

        Gap today: the single positional "What is the architecture?" is parsed as
        github_url; checkout and question are missing → INVALID_ARGUMENTS, exit 2.
        """
        checkout = _make_repo(self.root, "myrepo", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Architecture\n\nWhy: microservices.\n"})

        exit_code, report = _call_main(
            ["What is the architecture?"],
            cwd=checkout,
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(
            exit_code,
            0,
            msg=(
                f"Expected exit_code 0 (success), got {exit_code}. "
                f"Report: {report}. "
                "Likely cause: current parser rejects single-positional invocation."
            ),
        )
        self.assertTrue(
            report.get("ok"),
            msg=(
                f"Expected report.ok=True from cwd inference. Got: {report}. "
                "The new CLI surface is not yet implemented."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 2
    # ------------------------------------------------------------------

    def test_subdirectory_resolves_to_toplevel(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 2: when the path positional points to a subdirectory of the
        checkout, report.repository.checkout_path must equal the git toplevel,
        not the subdir.

        Gap today: str(subdir) is parsed as github_url (an invalid GitHub URL)
        → INVALID_GITHUB_URL, exit 2.
        """
        checkout = _make_repo(self.root, "myrepo", _GITHUB_REMOTE)
        subdir = checkout / "src"
        _commit(checkout, {"src/main.py": "# main\n", "README.md": "# Arch\n"})

        exit_code, report = _call_main(
            [str(subdir), "What is the architecture?"],
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(
            exit_code,
            0,
            msg=(
                f"Expected exit_code 0 when path arg is a subdir. Got {exit_code}. "
                f"Report: {report}."
            ),
        )
        self.assertTrue(report.get("ok"), msg=f"Expected ok=True. Report: {report}")
        reported_path = report.get("repository", {}).get("checkout_path", "")
        self.assertEqual(
            reported_path,
            str(checkout.resolve()),
            msg=(
                f"checkout_path must resolve to the git toplevel {checkout!s}, "
                f"not the subdir {subdir!s}. Got: {reported_path!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 3
    # ------------------------------------------------------------------

    def test_non_git_cwd_returns_json_error(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 3: cwd that is NOT inside any git repository must produce JSON
        output with ok=False, error.code=NOT_GIT_REPOSITORY, and exit code 2
        — no traceback.

        Gap today: the current parser fires first and returns INVALID_ARGUMENTS
        (missing checkout/question/--repositories-root positionals), not
        NOT_GIT_REPOSITORY.
        """
        non_git_dir = self.root / "plain_dir"
        non_git_dir.mkdir()

        exit_code, report = _call_main(
            ["What is the architecture?"],
            cwd=non_git_dir,
        )

        self.assertEqual(
            exit_code,
            2,
            msg=f"Expected exit_code 2. Got {exit_code}. Report: {report}",
        )
        self.assertFalse(report.get("ok"), msg="Expected ok=False for non-git cwd.")
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.NOT_GIT_REPOSITORY),
            msg=(
                f"Expected error.code=NOT_GIT_REPOSITORY, got "
                f"{report.get('error', {}).get('code')!r}. "
                "Today: parser fires before any git check → INVALID_ARGUMENTS."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 4
    # ------------------------------------------------------------------

    def test_inferred_identity_adds_derived_warning(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 4 / plan constraint 2: when the GitHub URL is inferred from
        remote.origin.url (no --github-url flag), the returned report must include
        a warning containing "derived" (case-insensitive), proving identity was not
        externally verified.

        Gap today: the parser fails before any inference occurs; report.ok is False.
        """
        checkout = _make_repo(self.root, "myrepo", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Architecture\n"})

        exit_code, report = _call_main(
            ["What is the architecture?"],
            cwd=checkout,
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertTrue(
            report.get("ok"),
            msg=(
                f"Expected ok=True for inferred-identity invocation. "
                f"Got: {report}. "
                "The new CLI surface is not yet implemented."
            ),
        )
        warnings_text = " ".join(report.get("warnings", [])).casefold()
        self.assertIn(
            "derived",
            warnings_text,
            msg=(
                "Expected a warning containing 'derived' for inferred identity "
                "(plan constraint 2). "
                f"Got warnings: {report.get('warnings')!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 5
    # ------------------------------------------------------------------

    def test_no_origin_without_github_url_flag_errors(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 5 / plan constraint 3: a checkout with NO remote origin and no
        --github-url flag must produce INVALID_ARGUMENTS.  The error must NOT
        contain a fabricated URL.

        Gap today: the argparse parser fires before the resolver and also returns
        INVALID_ARGUMENTS — but its error reason contains "required" (referring to
        missing positionals), not to the missing origin.  The assertion on the
        reason text distinguishes the two failure modes and FAILS today.
        """
        checkout = _make_repo(self.root, "no_origin", remote=None)
        _commit(checkout, {"README.md": "# No origin\n"})

        exit_code, report = _call_main(
            ["What is the architecture?"],
            cwd=checkout,
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(
            exit_code,
            2,
            msg=f"Expected exit_code 2 for no-origin error. Got {exit_code}.",
        )
        self.assertFalse(report.get("ok"), msg="Expected ok=False for no-origin.")
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.INVALID_ARGUMENTS),
            msg=(
                f"Expected INVALID_ARGUMENTS. "
                f"Got: {report.get('error', {}).get('code')!r}."
            ),
        )
        # Key differentiator: the new resolver emits an origin-related reason,
        # not argparse's "the following arguments are required: checkout, question"
        # message.  Today, argparse fires first and the reason text contains
        # "required", so this assertion FAILS.
        reason = report.get("error", {}).get("details", {}).get("reason", "")
        self.assertNotIn(
            "required",
            reason.lower(),
            msg=(
                "The INVALID_ARGUMENTS error must describe the missing origin, "
                "not argparse's missing-positionals message. "
                f"Got reason: {reason!r}. "
                "This assertion fails today because the new CLI surface is not implemented."
            ),
        )


# ---------------------------------------------------------------------------
# Criteria 6–10: re-proven safety invariants via new CLI surface
# ---------------------------------------------------------------------------

class SafetyInvariantTests(unittest.TestCase):
    """
    Criteria 6–10: re-prove that existing safety contracts still hold through
    the new CLI surface.

    Criteria 6, 9, 10 FAIL today (new argument surface not implemented).
    Criteria 7–8 PASS today (criterion 7 uses the current CLI surface;
    criterion 8 is a pure unit test).
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    # ------------------------------------------------------------------
    # Criterion 6
    # ------------------------------------------------------------------

    def test_explicit_github_url_mismatch_raises_remote_mismatch(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 6: passing --github-url that disagrees with remote.origin.url
        must produce REMOTE_MISMATCH — the gate must remain meaningful when the
        caller asserts an explicit URL.
        Mirrors test_day2_safety.py::RemoteMismatchTests::test_mismatched_github_url_raises_remote_mismatch.

        Gap today: --github-url is not a recognised flag in the current parser →
        INVALID_ARGUMENTS (unrecognised argument), not REMOTE_MISMATCH.
        """
        checkout = _make_repo(
            self.root, "sample", "https://github.com/example/real.git"
        )
        _commit(checkout, {"README.md": "# Real repo\n"})

        exit_code, report = _call_main(
            [
                "--github-url",
                "https://github.com/example/different",
                "What is the architecture?",
            ],
            cwd=checkout,
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(exit_code, 2)
        self.assertFalse(report.get("ok"))
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.REMOTE_MISMATCH),
            msg=(
                f"Expected REMOTE_MISMATCH for mismatched --github-url. "
                f"Got: {report.get('error', {}).get('code')!r}. "
                "Today: --github-url is unrecognised → INVALID_ARGUMENTS."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 7
    # ------------------------------------------------------------------

    def test_protected_root_blocks_inferred_checkout(self) -> None:
        """
        EXPECTED TO PASS before implementation.

        Criterion 7: a checkout whose path is inside the explicitly configured protected
        root must be blocked with PROTECTED_ROOT_ACCESS even when repositories-root
        is inferred (or defaults).

        Uses the CURRENT CLI surface (old three-positional form) with
        _default_protected_root patched to simulate the checkout falling inside the
        protected root.  This proves the underlying safety mechanism exists and
        functions correctly, independently of the new CLI surface.

        Simulation layout:
          self.root/repos/      ← repositories_root
          self.root/repos/sample/  ← checkout (inside repos_root)
          patched protected_root = self.root/repos/  ← checkout is inside protected
        """
        repos_root = self.root / "repos"
        repos_root.mkdir()
        checkout = _make_repo(repos_root, "sample", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Protected\n"})

        exit_code, report = _call_main(
            [
                _GITHUB_URL,
                str(checkout),
                "What is the architecture?",
                "--repositories-root",
                str(repos_root),
            ],
            protected_root=repos_root,  # checkout is inside repos_root == protected
        )

        self.assertEqual(
            exit_code,
            2,
            msg=f"Expected exit_code 2 for PROTECTED_ROOT_ACCESS. Got {exit_code}.",
        )
        self.assertFalse(report.get("ok"))
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.PROTECTED_ROOT_ACCESS),
            msg=(
                f"Expected PROTECTED_ROOT_ACCESS when checkout is inside protected root. "
                f"Got: {report!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 8
    # ------------------------------------------------------------------

    def test_protected_root_comes_from_explicit_environment(self) -> None:
        """
        EXPECTED TO PASS before and after implementation.

        The protected root must come from explicit configuration. It must not be
        inferred from cwd, origin URL, repositories-root, or installed package
        layout.
        """
        from jarvis_engineering import cli as _cli

        with mock.patch.dict(os.environ, {"JARVIS_PROTECTED_ROOT": str(_SAFE_PROTECTED_ROOT)}):
            self.assertEqual(_cli._default_protected_root(), _SAFE_PROTECTED_ROOT)

    # ------------------------------------------------------------------
    # Criterion 9
    # ------------------------------------------------------------------

    def test_explicit_repositories_root_enables_checkout_outside_root_error(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 9: passing --repositories-root pointing to a directory that does
        NOT contain the checkout must produce CHECKOUT_OUTSIDE_ROOT.  This proves
        the gate remains reachable via an explicit --repositories-root flag even
        when repositories-root would otherwise default to the checkout's parent.

        Gap today: the new path positional doesn't exist; the current parser parses
        str(checkout) as github_url (invalid GitHub URL format) → INVALID_GITHUB_URL,
        not CHECKOUT_OUTSIDE_ROOT.
        """
        checkout = _make_repo(self.root, "myrepo", _GITHUB_REMOTE)
        _commit(checkout, {"README.md": "# Repo\n"})

        # other_root exists but does NOT contain the checkout
        other_root = self.root / "other_root"
        other_root.mkdir()

        exit_code, report = _call_main(
            [
                str(checkout),
                "What is the architecture?",
                "--repositories-root",
                str(other_root),
            ],
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(exit_code, 2)
        self.assertFalse(report.get("ok"))
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.CHECKOUT_OUTSIDE_ROOT),
            msg=(
                f"Expected CHECKOUT_OUTSIDE_ROOT when --repositories-root excludes the checkout. "
                f"Got: {report.get('error', {}).get('code')!r}. "
                "Today: str(checkout) is parsed as github_url → INVALID_GITHUB_URL."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 10
    # ------------------------------------------------------------------

    def test_jsonl_in_inferred_path_is_blocked(self) -> None:
        """
        EXPECTED TO FAIL before implementation.

        Criterion 10: a path positional containing .jsonl in any component must
        produce JSONL_ACCESS_DENIED.  The check must fire before any git or
        network operation.

        Gap today: the path positional does not exist; /some/data.jsonl/repo is
        parsed as github_url (an invalid HTTPS GitHub URL) →  INVALID_GITHUB_URL,
        not JSONL_ACCESS_DENIED.
        """
        exit_code, report = _call_main(
            ["/some/data.jsonl/repo", "What is the architecture?"],
            protected_root=_SAFE_PROTECTED_ROOT,
        )

        self.assertEqual(exit_code, 2)
        self.assertFalse(report.get("ok"))
        self.assertEqual(
            report.get("error", {}).get("code"),
            str(ErrorCode.JSONL_ACCESS_DENIED),
            msg=(
                f"Expected JSONL_ACCESS_DENIED for path containing .jsonl. "
                f"Got: {report.get('error', {}).get('code')!r}. "
                "Today: the path arg is parsed as github_url → INVALID_GITHUB_URL."
            ),
        )


# ---------------------------------------------------------------------------
# Criteria 11–12: static properties and API stability
# ---------------------------------------------------------------------------

class StaticPropertyTests(unittest.TestCase):
    """
    Criteria 11–12: static and API properties that must hold before and after
    implementation.  BOTH tests are EXPECTED TO PASS today.
    """

    # ------------------------------------------------------------------
    # Criterion 11
    # ------------------------------------------------------------------

    def test_no_new_dependencies_in_pyproject(self) -> None:
        """
        EXPECTED TO PASS before and after implementation.

        Criterion 11: pyproject.toml [project].dependencies must remain an empty
        list.  The product is stdlib-only; no third-party packages are permitted.
        tomllib is a stdlib module since Python 3.11 (the project's minimum).
        """
        import tomllib

        pyproject = PROJECT_ROOT / "pyproject.toml"
        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)

        dependencies = data.get("project", {}).get("dependencies", [])
        self.assertEqual(
            dependencies,
            [],
            msg=(
                f"pyproject.toml [project].dependencies must be empty (stdlib-only). "
                f"Found: {dependencies!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Criterion 12
    # ------------------------------------------------------------------

    def test_existing_suite_api_is_unchanged(self) -> None:
        """
        EXPECTED TO PASS before and after implementation.

        Criterion 12: inspect_repository must still accept the current three-positional
        API (github_url, checkout, repositories_root, question, *, limits, protected_root)
        and return a dict with the standard keys.

        This proves the library API is frozen while only the CLI argument surface
        changes.  The entire existing 64-test suite relies on this signature.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = _make_repo(root, "sample", _GITHUB_REMOTE)
            _commit(
                checkout,
                {"README.md": "# Arch\n\nWhy: decision was made here.\n"},
            )

            report = inspect_repository(
                _GITHUB_URL,
                str(checkout),
                str(root),
                "What is the architecture?",
                protected_root=PROJECT_ROOT.parent,
            )

        self.assertIsInstance(report, dict, msg="inspect_repository must return a dict.")
        self.assertTrue(
            report.get("ok"),
            msg=(
                f"inspect_repository with the existing 3-positional API must return "
                f"ok=True. Got: {report!r}."
            ),
        )
        for key in ("repository", "evidence", "findings", "warnings", "schema_version"):
            self.assertIn(
                key,
                report,
                msg=f"Report must contain top-level key {key!r}.",
            )


if __name__ == "__main__":
    unittest.main()
