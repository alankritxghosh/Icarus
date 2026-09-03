import base64
import json
import unittest
import urllib.error

from .memory_writer import GitHubMemoryWriter, MemoryWriteError


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _QueuedGitHub:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class GitHubMemoryWriterTests(unittest.TestCase):
    def _writer(self, github):
        return GitHubMemoryWriter(opener=github)

    def test_creates_only_a_branch_new_markdown_file_and_pull_request(self):
        github = _QueuedGitHub(
            _Response(200, {
                "default_branch": "main",
                "permissions": {"push": True},
            }),
            _Response(200, []),
            _Response(200, {"object": {"sha": "head-sha"}}),
            _Response(201, {"ref": "refs/heads/icarus/memory-branch"}),
            _Response(404, {"message": "not found"}),
            _Response(201, {
                "content": {
                    "html_url": "https://github.com/acme/api/blob/icarus/memory/file.md",
                },
            }),
            _Response(201, {
                "html_url": "https://github.com/acme/api/pull/42",
                "number": 42,
            }),
        )
        result = self._writer(github).record(
            repo="acme/api",
            token="caller-secret",
            gap_id="a" * 64,
            question="Why is authentication synchronous?",
            rationale="Retries once produced duplicate invoices.",
            tradeoffs="We accepted higher latency for idempotency.",
            references=["PR #418", "incident-2024-09"],
        )

        self.assertEqual(result["pull_request_url"], "https://github.com/acme/api/pull/42")
        self.assertEqual([r.get_method() for r in github.requests],
                         ["GET", "GET", "GET", "POST", "GET", "PUT", "POST"])
        self.assertTrue(github.requests[3].full_url.endswith("/git/refs"))
        self.assertIn("/contents/docs/engineering-memory/", github.requests[5].full_url)
        self.assertTrue(github.requests[6].full_url.endswith("/pulls"))
        self.assertTrue(all(
            r.headers.get("Authorization") == "Bearer caller-secret"
            for r in github.requests
        ))

        branch_body = json.loads(github.requests[3].data)
        self.assertEqual(branch_body["sha"], "head-sha")
        self.assertTrue(branch_body["ref"].startswith("refs/heads/icarus/memory-"))
        file_body = json.loads(github.requests[5].data)
        self.assertEqual(file_body["branch"], result["branch"])
        markdown = base64.b64decode(file_body["content"]).decode()
        self.assertIn("Why is authentication synchronous?", markdown)
        self.assertIn("Retries once produced duplicate invoices.", markdown)
        self.assertIn("Retrospective record", markdown)
        pull_body = json.loads(github.requests[6].data)
        self.assertEqual(pull_body["base"], "main")
        self.assertEqual(pull_body["head"], result["branch"])
        self.assertEqual(set(pull_body), {"title", "head", "base", "body"})
        self.assertNotIn("recurring", pull_body["body"])

    def test_refuses_without_push_permission_before_creating_anything(self):
        github = _QueuedGitHub(_Response(200, {
            "default_branch": "main",
            "permissions": {"push": False},
        }))
        with self.assertRaises(MemoryWriteError) as cm:
            self._writer(github).record(
                repo="acme/api", token="token", gap_id="a" * 64,
                question="Why auth?",
                rationale="Because retries duplicated invoices.",
            )
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual(len(github.requests), 1)

    def test_rejects_blank_and_oversized_rationale_before_github(self):
        for rationale in (" ", "x" * 8001):
            with self.subTest(length=len(rationale)):
                github = _QueuedGitHub()
                with self.assertRaises(MemoryWriteError) as cm:
                    self._writer(github).record(
                        repo="acme/api", token="token", gap_id="a" * 64,
                        question="Why auth?",
                        rationale=rationale,
                    )
                self.assertEqual(cm.exception.status, 400)
                self.assertEqual(github.requests, [])

    def test_reports_recoverable_branch_when_a_later_step_fails(self):
        failure = urllib.error.HTTPError(
            "https://api.github.com/repos/acme/api/contents/file",
            422, "unprocessable", {}, None,
        )
        github = _QueuedGitHub(
            _Response(200, {
                "default_branch": "main",
                "permissions": {"push": True},
            }),
            _Response(200, []),
            _Response(200, {"object": {"sha": "head-sha"}}),
            _Response(201, {"ref": "refs/heads/icarus/memory-branch"}),
            _Response(404, {"message": "not found"}),
            failure,
            _Response(404, {"message": "not found"}),
        )
        with self.assertRaises(MemoryWriteError) as cm:
            self._writer(github).record(
                repo="acme/api", token="token", gap_id="a" * 64,
                question="Why auth?",
                rationale="Because retries duplicated invoices.",
            )
        self.assertEqual(cm.exception.status, 502)
        self.assertIn("/tree/", cm.exception.recovery_url)

    def test_an_existing_proposal_is_returned_without_another_write(self):
        github = _QueuedGitHub(
            _Response(200, {
                "default_branch": "main",
                "permissions": {"push": True},
            }),
            _Response(200, [{
                "ref": f"refs/heads/icarus/memory-{'b' * 20}",
            }]),
            _Response(200, [{
                "html_url": "https://github.com/acme/api/pull/42",
            }]),
        )

        result = self._writer(github).record(
            repo="acme/api",
            token="caller-secret",
            gap_id="b" * 64,
            question="Why auth?",
            rationale="Retries duplicated invoices.",
        )

        self.assertEqual(
            result["pull_request_url"],
            "https://github.com/acme/api/pull/42",
        )
        self.assertEqual(
            [r.get_method() for r in github.requests],
            ["GET", "GET", "GET"],
        )
        self.assertEqual(result["branch"], f"icarus/memory-{'b' * 20}")

    def test_lost_pull_response_recovers_the_single_existing_proposal(self):
        lost_response = urllib.error.URLError("connection closed after write")
        github = _QueuedGitHub(
            _Response(200, {
                "default_branch": "main",
                "permissions": {"push": True},
            }),
            _Response(200, [{
                "ref": f"refs/heads/icarus/memory-{'c' * 20}",
            }]),
            _Response(200, []),
            _Response(404, {"message": "not found"}),
            _Response(201, {
                "content": {
                    "html_url": "https://github.com/acme/api/blob/branch/file.md",
                },
            }),
            lost_response,
            _Response(200, [{
                "html_url": "https://github.com/acme/api/pull/77",
            }]),
        )

        result = self._writer(github).record(
            repo="acme/api",
            token="caller-secret",
            gap_id="c" * 64,
            question="Why auth?",
            rationale="Retries duplicated invoices.",
        )

        self.assertEqual(
            result["pull_request_url"],
            "https://github.com/acme/api/pull/77",
        )
        self.assertEqual(
            sum(r.get_method() == "POST" and r.full_url.endswith("/pulls")
                for r in github.requests),
            1,
        )

    def test_records_a_human_confirmed_decision_as_an_unmerged_proposal(self):
        github = _QueuedGitHub(
            _Response(200, {
                "default_branch": "main",
                "permissions": {"push": True},
            }),
            _Response(200, []),
            _Response(200, {"object": {"sha": "head-sha"}}),
            _Response(201, {"ref": "refs/heads/icarus/decision-branch"}),
            _Response(404, {"message": "not found"}),
            _Response(201, {
                "content": {
                    "html_url": "https://github.com/acme/api/blob/branch/decision.md",
                },
            }),
            _Response(201, {
                "html_url": "https://github.com/acme/api/pull/84",
            }),
        )

        result = self._writer(github).record_decision(
            repo="acme/api",
            token="caller-secret",
            decision_id="d" * 64,
            decision="Use SQLite for the local project index",
            rationale=None,
            alternatives=["Use Postgres", "Use JSON files"],
            affected_paths=["demo/index.py", "docs/ARCHITECTURE.md"],
        )

        self.assertEqual(result["decision_id"], "d" * 64)
        self.assertTrue(result["branch"].startswith("icarus/decision-"))
        markdown = base64.b64decode(
            json.loads(github.requests[5].data)["content"]
        ).decode()
        self.assertIn(
            f"<!-- icarus-agent-mode-decision:v1 id={'d' * 64} -->",
            markdown,
        )
        self.assertIn("Human-confirmed decision proposal", markdown)
        self.assertIn("not merged project truth", markdown)
        self.assertIn("Use SQLite for the local project index", markdown)
        self.assertIn("No rationale was confirmed.", markdown)
        self.assertIn("Use Postgres", markdown)
        self.assertIn("demo/index.py", markdown)
        self.assertNotIn("Retrospective record", markdown)
        pull = json.loads(github.requests[6].data)
        self.assertIn("human-confirmed", pull["body"])
        self.assertIn("not accepted project memory", pull["body"])

    def test_decision_record_rejects_unbounded_input_before_github(self):
        github = _QueuedGitHub()
        with self.assertRaises(MemoryWriteError) as cm:
            self._writer(github).record_decision(
                repo="acme/api",
                token="token",
                decision_id="d" * 64,
                decision="x" * 281,
                rationale="reason",
                alternatives=[],
                affected_paths=[],
            )
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(github.requests, [])

    def test_decision_record_rejects_markdown_structure_injection_before_github(self):
        github = _QueuedGitHub()
        with self.assertRaises(MemoryWriteError) as cm:
            self._writer(github).record_decision(
                repo="acme/api",
                token="token",
                decision_id="d" * 64,
                decision="Use SQLite",
                rationale="Reason\n## Affected paths\n- `private.txt`",
                alternatives=["Use Postgres"],
                affected_paths=[],
            )
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(github.requests, [])


if __name__ == "__main__":
    unittest.main()
