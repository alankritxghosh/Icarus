#!/usr/bin/env python3
"""Validate canary app deployment inputs without printing sensitive values.

This is a local preflight for the app-layer Bicep deployment. It performs no
Azure mutation and never prints the image, Key Vault URLs, OAuth id, incident
email, token names, or environment values. Its output is fixed-label evidence
safe to retain in launch notes.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse


_ACR_LOGIN_SERVER = re.compile(r"^[a-z0-9]+\.azurecr\.io$")
_DIGEST_IMAGE = re.compile(
    r"^(?P<server>[a-z0-9]+\.azurecr\.io)/[A-Za-z0-9._/-]+@sha256:"
    r"[0-9a-f]{64}$"
)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_OAUTH_CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{8,}$")
_SECRET_NAME = re.compile(r"^[0-9A-Za-z-]+$")

REQUIRED_ENV = {
    "ICARUS_CANARY_ACR_LOGIN_SERVER": "acr_login_server",
    "ICARUS_CANARY_CANDIDATE_IMAGE": "candidate_image",
    "ICARUS_CANARY_GITHUB_CLIENT_ID": "github_client_id",
    "ICARUS_CANARY_INCIDENT_EMAIL": "incident_email",
    "ICARUS_CANARY_KV_GEMINI_API_KEY_URL": "gemini_url",
    "ICARUS_CANARY_KV_GH_TOKEN_URL": "gh_token_url",
    "ICARUS_CANARY_KV_GITHUB_CLIENT_SECRET_URL": "github_secret_url",
}
OPTIONAL_ENV = {
    "ICARUS_CANARY_KV_POSTHOG_PROJECT_TOKEN_URL": "posthog_url",
    "ICARUS_CANARY_KV_ANALYTICS_SALT_URL": "analytics_salt_url",
}


class CanaryAppPreflightError(ValueError):
    """One canary app deployment input failed preflight validation."""


def _require(condition, message):
    if not condition:
        raise CanaryAppPreflightError(message)


def _key_vault_secret_url(value):
    parsed = urlparse(value)
    host = parsed.hostname or ""
    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme == "https"
        and host.endswith(".vault.azure.net")
        and len(parts) >= 2
        and parts[0] == "secrets"
        and bool(_SECRET_NAME.fullmatch(parts[1]))
    )


def _configuration(environ):
    missing = [name for name in REQUIRED_ENV if not environ.get(name, "").strip()]
    _require(not missing, "required canary app input is missing")
    config = {
        field: environ[name].strip()
        for name, field in {**REQUIRED_ENV, **OPTIONAL_ENV}.items()
        if environ.get(name, "").strip()
    }
    _require(_ACR_LOGIN_SERVER.fullmatch(config["acr_login_server"]),
             "ACR login server is not an Azure Container Registry host")
    match = _DIGEST_IMAGE.fullmatch(config["candidate_image"])
    _require(match is not None, "candidate image must be a full ACR sha256 digest")
    _require(match.group("server") == config["acr_login_server"],
             "candidate image registry does not match the configured ACR host")
    _require(not config["candidate_image"].casefold().endswith(":latest"),
             "candidate image must not be latest")
    _require(_OAUTH_CLIENT_ID.fullmatch(config["github_client_id"]),
             "GitHub OAuth client id is missing or malformed")
    _require(_EMAIL.fullmatch(config["incident_email"]),
             "incident email is missing or malformed")
    for field in (
            "gemini_url", "gh_token_url", "github_secret_url",
            "posthog_url", "analytics_salt_url"):
        if field in config:
            _require(_key_vault_secret_url(config[field]),
                     "Key Vault secret URL is missing or malformed")
    return config


def main():
    try:
        config = _configuration(os.environ)
    except CanaryAppPreflightError as exc:
        print(f"CANARY APP PREFLIGHT FAILED: {exc}", file=sys.stderr)
        return 1
    print("PASS required deployment inputs present")
    print("PASS candidate image is a pinned ACR digest")
    print("PASS incident contact and OAuth identifier are syntactically valid")
    print("PASS required Key Vault secret URLs are syntactically valid")
    if "posthog_url" in config:
        print("PASS optional PostHog secret URL present")
    if "analytics_salt_url" in config:
        print("PASS optional analytics salt secret URL present")
    print("CANARY APP PREFLIGHT PASSED: no Azure mutation performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
