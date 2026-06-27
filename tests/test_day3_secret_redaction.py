"""
Day 3 adversarial tests: secret leakage in evidence excerpts.

Each test commits a file containing a raw secret value into a deterministic
temp git repo, calls inspect_repository, and asserts that the raw secret
string does NOT appear in any evidence[*]["excerpt"] in the returned report.

Tests that FAIL prove that the current redaction logic in evidence.py has a
gap and the raw secret would be visible in the returned JSON report.

Formats under test (8 total):
  1. JSON password field            — "password": "supersecret"
  2. HTTP Authorization Bearer      — Authorization: Bearer sk_live_abc123
  3. Function call argument         — getKey("sk_live_abc123")
  4. Bare API key in prose          — sk_live_abc123 handles all payment processing
  5. GitHub PAT in prose            — token ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345 is used for CI
  6. AWS AKIA key in prose          — access key AKIAIOSFODNN7EXAMPLE is configured
  7. Database URL with credentials  — postgresql://admin:hunter2@db.example.com:5432/mydb
  8. PEM private key block header   — -----BEGIN RSA PRIVATE KEY-----

Tests 1, 5, 6, 7, 8 are expected to PASS (already handled by the current
implementation).  Tests 2, 3, 4 are expected to FAIL (proven leakage gaps):
the raw string "sk_live_abc123" is not matched by any existing redaction
pattern in evidence._SECRET_ASSIGNMENT_RE or evidence._INLINE_SECRET_RES.
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

from jarvis_engineering.inspector import inspect_repository

_GITHUB_URL = "https://github.com/example/redaction-test-repo"


# ---------------------------------------------------------------------------
# Shared deterministic helpers (same pattern as test_day2_safety.py)
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
# Secret redaction gap tests
# ---------------------------------------------------------------------------

class SecretRedactionGapTests(unittest.TestCase):
    """
    Prove that raw secret values do not appear in evidence[*]["excerpt"].

    Methodology: commit a single file containing a known secret string,
    call inspect_repository, scan every evidence excerpt for the raw secret.

    No remote is set on the temp repos; inspect_repository emits an
    unverified-identity warning but proceeds normally (confirmed by
    test_day2_safety.py::RemoteMismatchTests::test_no_remote_origin_emits_warning_not_error).
    """

    _QUESTION = "What is the service architecture?"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _inspect(self, files: dict[str, str]) -> dict:
        """Create a fresh repo, commit files, and run inspect_repository."""
        checkout = _make_repo(self.root, "sample")  # no remote — warning only
        _commit(checkout, files)
        return inspect_repository(
            _GITHUB_URL,
            "sample",
            str(self.root),
            self._QUESTION,
            protected_root=PROJECT_ROOT.parent,
        )

    def _assert_secret_absent(self, report: dict, secret: str) -> None:
        """
        Assert that the raw secret string does not appear in any evidence excerpt.
        A failure here means the secret is visible in the returned JSON report.
        """
        self.assertIn("evidence", report, msg="Report must have an evidence key.")
        leaking_excerpts = [
            item["excerpt"]
            for item in report["evidence"]
            if secret in item["excerpt"]
        ]
        self.assertEqual(
            leaking_excerpts,
            [],
            msg=(
                f"Raw secret {secret!r} leaked into {len(leaking_excerpts)} "
                f"evidence excerpt(s):\n"
                + "\n---\n".join(leaking_excerpts)
            ),
        )

    # ------------------------------------------------------------------
    # Format 1: JSON password field
    # Expected: PASS — _SECRET_ASSIGNMENT_RE matches "password": on the left
    #           of the colon assignment and redacts the value.
    # ------------------------------------------------------------------

    def test_json_password_field_is_redacted(self) -> None:
        """
        A JSON file with `"password": "supersecret"` must not expose
        'supersecret' in any evidence excerpt.

        _SECRET_ASSIGNMENT_RE includes 'password' as a key-side keyword and
        matches `"password": ` as the prefix, replacing the value with
        [REDACTED].  config.json is classified as 'configuration' by
        evidence._classify (suffix .json, name starts with 'config').
        """
        report = self._inspect({
            "config.json": (
                '{\n'
                '  "password": "supersecret",\n'
                '  "host": "db.example.com",\n'
                '  "port": 5432\n'
                '}\n'
            ),
        })
        self._assert_secret_absent(report, "supersecret")

    # ------------------------------------------------------------------
    # Format 2: HTTP Authorization Bearer header in source code
    # Expected: FAIL — 'sk_live_abc123' is not matched by
    #           _SECRET_ASSIGNMENT_RE (key side is 'Authorization', not a
    #           recognised keyword) nor by any pattern in _INLINE_SECRET_RES
    #           (not a gh[pousr]_ token, AKIA key, or database URL).
    # ------------------------------------------------------------------

    def test_bearer_token_in_source_code_leaks(self) -> None:
        """
        A Python source file containing `{"Authorization": "Bearer sk_live_abc123"}`
        must not expose 'sk_live_abc123' in any evidence excerpt.

        CURRENT GAP: 'Authorization' is not in _SECRET_ASSIGNMENT_RE's keyword
        list, so the line is not caught by the assignment pattern.
        'sk_live_abc123' is not a GitHub PAT, AKIA key, or database URL, so
        none of _INLINE_SECRET_RES patterns match it either.  The raw Stripe
        live key is emitted verbatim into the excerpt.

        Expected to FAIL against the current implementation.
        """
        report = self._inspect({
            "src/api_client.py": (
                "# Service API client architecture component\n"
                "import requests\n"
                "\n"
                "def make_request(url):\n"
                '    headers = {"Authorization": "Bearer sk_live_abc123"}\n'
                "    return requests.get(url, headers=headers)\n"
            ),
        })
        self._assert_secret_absent(report, "sk_live_abc123")

    # ------------------------------------------------------------------
    # Format 3: API key as a function call argument
    # Expected: FAIL — same gap as format 2; no pattern catches a bare
    #           sk_live_* string inside a function call.
    # ------------------------------------------------------------------

    def test_function_call_key_argument_leaks(self) -> None:
        """
        A Python source file containing `getKey("sk_live_abc123")` must not
        expose 'sk_live_abc123' in any evidence excerpt.

        CURRENT GAP: _SECRET_ASSIGNMENT_RE requires a key=value or key:value
        pattern; a bare string inside a function call has no assignment
        operator and is not matched.  _INLINE_SECRET_RES has no pattern that
        matches the sk_live_ prefix.

        Expected to FAIL against the current implementation.
        """
        report = self._inspect({
            "src/payment.py": (
                "# Payment service architecture component\n"
                "def setup_payment():\n"
                '    key = getKey("sk_live_abc123")\n'
                "    return key\n"
            ),
        })
        self._assert_secret_absent(report, "sk_live_abc123")

    # ------------------------------------------------------------------
    # Format 4: Bare API key as the subject of a prose sentence
    # Expected: FAIL — same gap; the bare sk_live_* string at the start of
    #           a sentence has no surrounding assignment syntax.
    # ------------------------------------------------------------------

    def test_bare_api_key_in_prose_leaks(self) -> None:
        """
        A README.md whose body starts with 'sk_live_abc123 handles all
        payment processing' must not expose 'sk_live_abc123' in any excerpt.

        CURRENT GAP: _SECRET_ASSIGNMENT_RE requires an assignment operator;
        a bare token used as a sentence subject is not matched.
        _INLINE_SECRET_RES has no sk_live_ pattern.  The token appears
        verbatim in the excerpt window because _STRUCTURE_RE matches
        'Architecture' in the heading, placing the first line (index 0) as
        focus and pulling in the next 11 lines, which include the secret.

        Expected to FAIL against the current implementation.
        """
        report = self._inspect({
            "README.md": (
                "# Payment Service Architecture\n"
                "\n"
                "sk_live_abc123 handles all payment processing via Stripe.\n"
            ),
        })
        self._assert_secret_absent(report, "sk_live_abc123")

    # ------------------------------------------------------------------
    # Format 5: GitHub Personal Access Token in prose
    # Expected: PASS — _INLINE_SECRET_RES includes
    #           re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{10,}\b")
    #           which matches ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345.
    # ------------------------------------------------------------------

    def test_github_pat_in_prose_is_redacted(self) -> None:
        """
        A README.md line 'token ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345 is used
        for CI' must not expose the raw PAT in any evidence excerpt.

        The inline regex \bgh[pousr]_[A-Za-z0-9_]{10,}\b matches the 32-char
        suffix and the full token is replaced with [REDACTED].
        """
        report = self._inspect({
            "README.md": (
                "# CI Pipeline Architecture\n"
                "\n"
                "The token ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345 is used for CI.\n"
            ),
        })
        self._assert_secret_absent(report, "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345")

    # ------------------------------------------------------------------
    # Format 6: AWS AKIA access key in prose
    # Expected: PASS — _INLINE_SECRET_RES includes
    #           re.compile(r"\bAKIA[0-9A-Z]{12,}\b")
    #           which matches AKIAIOSFODNN7EXAMPLE (16-char suffix).
    # ------------------------------------------------------------------

    def test_aws_akia_key_in_prose_is_redacted(self) -> None:
        """
        A README.md line 'access key AKIAIOSFODNN7EXAMPLE is configured' must
        not expose the raw AKIA key in any evidence excerpt.

        The inline regex \bAKIA[0-9A-Z]{12,}\b matches the 16-char suffix
        and the key is replaced with [REDACTED].
        """
        report = self._inspect({
            "README.md": (
                "# AWS Infrastructure Architecture\n"
                "\n"
                "The access key AKIAIOSFODNN7EXAMPLE is configured for S3 access.\n"
            ),
        })
        self._assert_secret_absent(report, "AKIAIOSFODNN7EXAMPLE")

    # ------------------------------------------------------------------
    # Format 7: PostgreSQL database URL with embedded credentials
    # Expected: PASS — _INLINE_SECRET_RES includes
    #           re.compile(r"\bpostgres(?:ql)?://[^:\s/@]+:[^@\s]+@[^\s\"']+")
    #           which matches the full URL, including the 'hunter2' password.
    # ------------------------------------------------------------------

    def test_database_url_credentials_are_redacted(self) -> None:
        """
        A README.md line containing
        'postgresql://admin:hunter2@db.example.com:5432/mydb' must not expose
        the password 'hunter2' in any evidence excerpt.

        The postgres inline regex matches the entire URL (including the
        credential segment) and replaces it with [REDACTED], so 'hunter2'
        does not appear in the output.
        """
        report = self._inspect({
            "README.md": (
                "# Database Architecture\n"
                "\n"
                "Connect to postgresql://admin:hunter2@db.example.com:5432/mydb.\n"
            ),
        })
        self._assert_secret_absent(report, "hunter2")

    # ------------------------------------------------------------------
    # Format 8: PEM private key BEGIN header line
    # Expected: PASS — _excerpt() detects -----BEGIN [A-Z ]*PRIVATE KEY-----
    #           via _PRIVATE_KEY_BEGIN_RE, appends '[REDACTED PRIVATE KEY BLOCK]',
    #           sets in_private_key=True, and skips all subsequent lines until
    #           the matching END marker.
    # ------------------------------------------------------------------

    def test_pem_private_key_block_is_redacted(self) -> None:
        """
        A settings.txt file whose body contains a PEM RSA private key block
        must not expose the header line '-----BEGIN RSA PRIVATE KEY-----'
        in any evidence excerpt.

        _PRIVATE_KEY_BEGIN_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
        matches the RSA variant and triggers block-level redaction in _excerpt.
        settings.txt is classified as 'configuration' by evidence._classify
        (suffix .txt, name starts with 'settings').
        """
        report = self._inspect({
            "settings.txt": (
                "# Authentication key for service architecture\n"
                "\n"
                "-----BEGIN RSA PRIVATE KEY-----\n"
                "MIIEowIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyz\n"
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
                "-----END RSA PRIVATE KEY-----\n"
            ),
        })
        self._assert_secret_absent(report, "-----BEGIN RSA PRIVATE KEY-----")


if __name__ == "__main__":
    unittest.main()
