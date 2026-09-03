#!/usr/bin/env python3
"""Run Icarus's two-identity/four-repository launch-canary matrix.

The harness never prints tokens, repository slugs, questions, answers, evidence,
or response bodies. It labels repositories P/A-private/B-private/shared in its
output and fails on the first authorization, isolation, or cite-or-unknown
violation. Running it indexes the explicitly configured disposable repos on the
target service, so the CLI requires an explicit acknowledgement.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


_SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ACK = "I-authorized-this-canary-run"


class CanaryFailure(RuntimeError):
    """One observed canary invariant failed."""


def _require(condition, message):
    if not condition:
        raise CanaryFailure(message)


def _contains(value, needle):
    return needle.casefold() in json.dumps(value, ensure_ascii=False).casefold()


class CanaryAcceptance:
    def __init__(self, transport, *, token_a, token_b, repos, timeout=300,
                 clock=time.monotonic, pause=time.sleep, report=print):
        self.call = transport
        self.a = token_a
        self.b = token_b
        self.repos = repos
        self.timeout = timeout
        self.clock = clock
        self.pause = pause
        self.report = report

    def _step(self, label):
        self.report(f"PASS {label}")

    def _call(self, token, method, path, body):
        result = self.call(token, method, path, body)
        if len(result) == 2:
            status, payload = result
            return status, payload, {}
        status, payload, headers = result
        return status, payload, {str(k).casefold(): str(v) for k, v in headers.items()}

    def _status(self, token):
        status, body, _headers = self._call(token, "GET", "/status", None)
        _require(status == 200 and isinstance(body, dict), "status failed")
        return body

    def _connect(self, token, repo, label):
        status, _body, _headers = self._call(
            token, "POST", "/connect", {"repo": repo})
        _require(status in (200, 202), f"{label} connect failed with {status}")
        deadline = self.clock() + self.timeout
        while self.clock() < deadline:
            snapshot = self._status(token)
            if snapshot.get("state") == "error":
                raise CanaryFailure(f"{label} indexing entered error state")
            if (snapshot.get("state") == "ready"
                    and str(snapshot.get("repo", "")).casefold() == repo.casefold()):
                return snapshot
            self.pause(2)
        raise CanaryFailure(f"{label} indexing timed out")

    def _denied_connect(self, token, repo, label):
        status, body, _headers = self._call(
            token, "POST", "/connect", {"repo": repo})
        _require(status == 403, f"{label} expected 403, got {status}")
        _require(not _contains(body, repo), f"{label} leaked denied repository metadata")

    def _ask(self, token, label):
        status, body, _headers = self._call(
            token, "POST", "/ask", {"question": "What is this project's purpose?"})
        _require(status == 200 and isinstance(body, dict),
                 f"{label} ask failed with {status}")
        verdict = body.get("verdict")
        _require(verdict in {"answer", "unknown"}, f"{label} has invalid verdict")
        if verdict == "answer":
            _require(bool(body.get("answer")), f"{label} answer is empty")
            _require(bool(body.get("citations")), f"{label} answer has no citation")
        else:
            _require(not body.get("answer"), f"{label} unknown carried an answer")
        return body

    def run(self):
        status, _body, _headers = self._call(None, "GET", "/health", None)
        _require(status == 200, f"health returned {status}")
        status, _body, _headers = self._call(None, "GET", "/ready", None)
        _require(status == 200, f"readiness returned {status}")
        self._step("health and readiness")

        status, body, _headers = self._call(None, "GET", "/status", None)
        _require(status == 401, f"anonymous status expected 401, got {status}")
        for repo in self.repos.values():
            _require(not _contains(body, repo), "anonymous response leaked repository metadata")
        self._step("anonymous caller denied")

        public = self.repos["public"]
        self._connect(self.a, public, "A/public")
        self._ask(self.a, "A/public")
        self._connect(self.b, public, "B/public")
        self._ask(self.b, "B/public")
        self._step("public repository works for both identities")

        a_private = self.repos["a_private"]
        self._connect(self.a, a_private, "A/A-private")
        self._ask(self.a, "A/A-private")
        self._denied_connect(self.b, a_private, "B/A-private")
        _require(self._status(self.b).get("repo", "").casefold() == public.casefold(),
                 "B moved repositories after denied A-private connect")
        self._step("A-private is isolated from B")

        b_private = self.repos["b_private"]
        self._connect(self.b, b_private, "B/B-private")
        self._ask(self.b, "B/B-private")
        self._denied_connect(self.a, b_private, "A/B-private")
        _require(self._status(self.a).get("repo", "").casefold() == a_private.casefold(),
                 "A moved repositories after denied B-private connect")
        self._step("B-private is isolated from A")

        status, session, _headers = self._call(
            self.a, "POST", "/auth/agent/session", {})
        _require(status == 200 and isinstance(session.get("token"), str),
                 "could not mint A's repo-scoped agent session")
        agent_token = session["token"]

        shared = self.repos["shared"]
        self._connect(self.a, shared, "A/shared")
        self._connect(self.b, shared, "B/shared")
        self._ask(self.a, "A/shared")
        self._ask(self.b, "B/shared")
        status, body, _headers = self._call(
            agent_token, "POST", "/ask", {"question": "What is this project's purpose?"})
        _require(status == 403, f"stale repo-scoped agent grant expected 403, got {status}")
        _require(not _contains(body, shared), "agent denial leaked current repository metadata")
        self._step("shared memory works and agent grant cannot follow repo switch")

        status, _body, _headers = self._call(
            self.a, "POST", "/disconnect", {})
        _require(status == 200, f"A disconnect returned {status}")
        a_after = self._status(self.a)
        _require(a_after.get("repo", "").casefold() != shared.casefold(),
                 "A disconnect retained the shared repo pointer")
        _require(self._status(self.b).get("repo", "").casefold() == shared.casefold(),
                 "A disconnect moved B off the shared repository")
        self._ask(self.b, "B/shared after A disconnect")
        self._step("disconnect removes A state without destroying shared memory")

        rejected = None
        for _attempt in range(3):
            status, body, headers = self._call(
                self.a, "POST", "/connect", {"repo": public})
            if status == 429:
                rejected = (body, headers)
                break
            _require(status in (200, 202),
                     f"rate-limit probe connect returned {status}")
        _require(rejected is not None, "per-identity connect limit did not reject")
        body, headers = rejected
        retry_after = headers.get("retry-after", "")
        _require(retry_after.isdigit() and int(retry_after) > 0,
                 "429 response omitted a positive Retry-After")
        _require(not any(_contains(body, repo) for repo in self.repos.values()),
                 "429 response leaked repository metadata")
        self._step("live per-identity limit returns leak-safe 429 with Retry-After")

        return {"passed": 8}


def _http_transport(base):
    base = base.rstrip("/")

    def call(token, method, path, body):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return response.status, json.loads(raw or b"{}"), dict(response.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                payload = {"error": "non-json response"}
            return exc.code, payload, dict(exc.headers)

    return call


def _configuration(environ):
    base = environ.get("ICARUS_CANARY_BASE", "").strip()
    parsed = urllib.parse.urlparse(base)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise CanaryFailure("canary base must use HTTPS (HTTP is allowed only locally)")
    token_a = environ.get("ICARUS_CANARY_TOKEN_A", "").strip()
    token_b = environ.get("ICARUS_CANARY_TOKEN_B", "").strip()
    _require(token_a and token_b and token_a != token_b,
             "two distinct canary bearer tokens are required")
    names = {
        "public": "ICARUS_CANARY_REPO_PUBLIC",
        "a_private": "ICARUS_CANARY_REPO_A_PRIVATE",
        "b_private": "ICARUS_CANARY_REPO_B_PRIVATE",
        "shared": "ICARUS_CANARY_REPO_SHARED",
    }
    repos = {key: environ.get(env, "").strip() for key, env in names.items()}
    _require(all(_SAFE_REPO.fullmatch(repo or "") and ".." not in repo
                 for repo in repos.values()), "all four disposable repos are required")
    _require(len({repo.casefold() for repo in repos.values()}) == 4,
             "the four canary repositories must be distinct")
    _require(environ.get("ICARUS_CANARY_ACK") == _ACK,
             f"set ICARUS_CANARY_ACK={_ACK} after authorizing this run")
    return base, token_a, token_b, repos


def main():
    try:
        base, token_a, token_b, repos = _configuration(os.environ)
        result = CanaryAcceptance(
            _http_transport(base), token_a=token_a, token_b=token_b, repos=repos,
        ).run()
    except CanaryFailure as exc:
        print(f"CANARY FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # no response body, URL, token or repo in output
        print(f"CANARY FAILED: transport {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"CANARY PASSED: {result['passed']} adversarial gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
