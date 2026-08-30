"""Canary app preflight is strict, local, and content-free."""

import io
from contextlib import redirect_stderr, redirect_stdout
import os
import unittest

from scripts.canary_app_preflight import (
    CanaryAppPreflightError,
    _configuration,
    main,
)


_DIGEST = "a" * 64


def _healthy_env():
    return {
        "ICARUS_CANARY_ACR_LOGIN_SERVER": "registry123.azurecr.io",
        "ICARUS_CANARY_CANDIDATE_IMAGE": (
            f"registry123.azurecr.io/icarus-brain@sha256:{_DIGEST}"
        ),
        "ICARUS_CANARY_GITHUB_CLIENT_ID": "Iv1abcdefgh",
        "ICARUS_CANARY_INCIDENT_EMAIL": "incident@example.com",
        "ICARUS_CANARY_KV_GEMINI_API_KEY_URL": (
            "https://vault.vault.azure.net/secrets/gemini-api-key"
        ),
        "ICARUS_CANARY_KV_GH_TOKEN_URL": (
            "https://vault.vault.azure.net/secrets/gh-token"
        ),
        "ICARUS_CANARY_KV_GITHUB_CLIENT_SECRET_URL": (
            "https://vault.vault.azure.net/secrets/github-client-secret"
        ),
    }


class CanaryAppPreflightTests(unittest.TestCase):
    def test_healthy_inputs_pass(self):
        config = _configuration(_healthy_env())
        self.assertEqual(config["acr_login_server"], "registry123.azurecr.io")

    def test_rejects_mutable_or_wrong_registry_images(self):
        cases = {
            "tag": "registry123.azurecr.io/icarus-brain:abcdef1",
            "latest": "registry123.azurecr.io/icarus-brain:latest",
            "wrong registry": f"other.azurecr.io/icarus-brain@sha256:{_DIGEST}",
        }
        for label, image in cases.items():
            with self.subTest(label=label):
                env = _healthy_env()
                env["ICARUS_CANARY_CANDIDATE_IMAGE"] = image
                with self.assertRaises(CanaryAppPreflightError):
                    _configuration(env)

    def test_rejects_missing_or_malformed_secrets_without_printing_values(self):
        env = _healthy_env()
        secret = env["ICARUS_CANARY_KV_GH_TOKEN_URL"]
        env["ICARUS_CANARY_KV_GH_TOKEN_URL"] = "https://example.com/not-vault"
        with self.assertRaisesRegex(CanaryAppPreflightError, "Key Vault"):
            _configuration(env)
        original = os.environ.copy()
        out = io.StringIO()
        err = io.StringIO()
        try:
            os.environ.clear()
            os.environ.update(env)
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(), 1)
        finally:
            os.environ.clear()
            os.environ.update(original)
        self.assertNotIn(secret, out.getvalue())
        self.assertNotIn(secret, err.getvalue())

    def test_stdout_contains_only_fixed_labels(self):
        env = _healthy_env()
        env["ICARUS_CANARY_KV_POSTHOG_PROJECT_TOKEN_URL"] = (
            "https://vault.vault.azure.net/secrets/posthog-project-token"
        )
        original = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(env)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(), 0)
        finally:
            os.environ.clear()
            os.environ.update(original)
        rendered = out.getvalue()
        for value in env.values():
            self.assertNotIn(value, rendered)
        self.assertIn("CANARY APP PREFLIGHT PASSED", rendered)


if __name__ == "__main__":
    unittest.main()
