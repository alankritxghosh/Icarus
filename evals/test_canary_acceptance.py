"""The live canary matrix is complete, repeatable, and leak-safe."""

import unittest

from scripts.canary_acceptance import (
    CanaryAcceptance,
    CanaryFailure,
    _configuration,
)


class _CanaryService:
    A = "token-a-secret"
    B = "token-b-secret"
    AGENT = "short-agent-secret"

    def __init__(self, repos):
        self.repos = repos
        self.active = {self.A: "default/repo", self.B: "default/repo"}
        self.connects = {self.A: 0, self.B: 0}
        self.agent_bound = None

    def __call__(self, token, method, path, body):
        if path in {"/health", "/ready"}:
            return 200, {"ok": True}
        if token is None:
            return 401, {"error": "sign in"}
        if path == "/status":
            return 200, {"state": "ready", "repo": self.active[token]}
        if path == "/connect":
            if self.connects[token] >= 5:
                return 429, {"error": "slow down"}, {"Retry-After": "600"}
            self.connects[token] += 1
            repo = body["repo"]
            allowed = (
                repo in {self.repos["public"], self.repos["shared"]}
                or (token == self.A and repo == self.repos["a_private"])
                or (token == self.B and repo == self.repos["b_private"])
            )
            if not allowed:
                return 403, {"error": "not authorized"}
            self.active[token] = repo
            return 202, {"state": "indexing"}
        if path == "/auth/agent/session":
            self.agent_bound = self.active[token]
            return 200, {"token": self.AGENT, "repo": self.agent_bound}
        if path == "/ask":
            if token == self.AGENT:
                if self.active[self.A] != self.agent_bound:
                    return 403, {"error": "repo-scoped grant"}
            return 200, {
                "verdict": "answer", "answer": "Grounded.",
                "citations": [{"ref": "issue:1"}],
            }
        if path == "/disconnect":
            self.active[token] = "default/repo"
            return 200, {"state": "ready", "repo": "default/repo"}
        raise AssertionError((token, method, path, body))


class CanaryAcceptanceTests(unittest.TestCase):
    REPOS = {
        "public": "open/public-project",
        "a_private": "alpha/private-a",
        "b_private": "beta/private-b",
        "shared": "team/shared-private",
    }

    def test_complete_two_identity_four_repo_matrix(self):
        output = []
        service = _CanaryService(self.REPOS)
        result = CanaryAcceptance(
            service, token_a=service.A, token_b=service.B, repos=self.REPOS,
            pause=lambda _seconds: None, report=output.append,
        ).run()
        self.assertEqual(result, {"passed": 8})
        self.assertEqual(len(output), 8)
        rendered = "\n".join(output)
        for secret in (service.A, service.B, service.AGENT, *self.REPOS.values()):
            self.assertNotIn(secret, rendered)

    def test_answer_without_citations_fails_the_canary(self):
        service = _CanaryService(self.REPOS)
        original = service.__call__

        def uncited(token, method, path, body):
            status, payload = original(token, method, path, body)
            if path == "/ask" and status == 200:
                payload = {"verdict": "answer", "answer": "Unsupported", "citations": []}
            return status, payload

        with self.assertRaisesRegex(CanaryFailure, "no citation"):
            CanaryAcceptance(
                uncited, token_a=service.A, token_b=service.B, repos=self.REPOS,
                pause=lambda _seconds: None, report=lambda _line: None,
            ).run()

    def test_denial_that_echoes_private_repo_is_a_failure(self):
        service = _CanaryService(self.REPOS)
        original = service.__call__

        def leaking(token, method, path, body):
            status, payload = original(token, method, path, body)
            if path == "/connect" and status == 403:
                return status, {"error": f"cannot read {body['repo']}"}
            return status, payload

        with self.assertRaisesRegex(CanaryFailure, "leaked"):
            CanaryAcceptance(
                leaking, token_a=service.A, token_b=service.B, repos=self.REPOS,
                pause=lambda _seconds: None, report=lambda _line: None,
            ).run()

    def test_configuration_requires_https_distinct_inputs_and_ack(self):
        base = {
            "ICARUS_CANARY_BASE": "https://canary.example",
            "ICARUS_CANARY_TOKEN_A": "a",
            "ICARUS_CANARY_TOKEN_B": "b",
            "ICARUS_CANARY_REPO_PUBLIC": self.REPOS["public"],
            "ICARUS_CANARY_REPO_A_PRIVATE": self.REPOS["a_private"],
            "ICARUS_CANARY_REPO_B_PRIVATE": self.REPOS["b_private"],
            "ICARUS_CANARY_REPO_SHARED": self.REPOS["shared"],
            "ICARUS_CANARY_ACK": "I-authorized-this-canary-run",
        }
        configured = _configuration(base)
        self.assertEqual(configured[0], "https://canary.example")
        with self.assertRaisesRegex(CanaryFailure, "HTTPS"):
            _configuration({**base, "ICARUS_CANARY_BASE": "http://canary.example"})
        with self.assertRaisesRegex(CanaryFailure, "distinct"):
            _configuration({**base, "ICARUS_CANARY_TOKEN_B": "a"})
        with self.assertRaisesRegex(CanaryFailure, "ACK"):
            _configuration({**base, "ICARUS_CANARY_ACK": ""})


if __name__ == "__main__":
    unittest.main()
