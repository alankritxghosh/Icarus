"""User-boundary tests for the Claude-first Agent Mode HTTP loop."""

import json
import tempfile
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

from evals.corpus import Chunk

from .agent_sessions import AgentSessionStore
from .auth import StaticTokenVerifier
from .decision_ledger import DecisionLedger
from .test_server import REPO, _RepoLibrary, _ServerFixture, _StubAccess


PRIVATE = "acme/agent-project"
GITHUB_TOKEN = "github-token"
IDENTITY = "1001"


class _DecisionWriter:
    def __init__(self):
        self.calls = []

    def record_decision(self, **kwargs):
        self.calls.append(kwargs)
        decision_id = kwargs["decision_id"]
        return {
            "repo": kwargs["repo"],
            "decision_id": decision_id,
            "branch": f"icarus/decision-{decision_id[:20]}",
            "path": f"docs/engineering-memory/{decision_id[:20]}-decision.md",
            "file_url": "https://github.com/acme/agent-project/blob/branch/decision.md",
            "pull_request_url": "https://github.com/acme/agent-project/pull/42",
        }


class _IndexedDecisionPipeline:
    def __init__(self, chunks):
        self._chunks = chunks

    def indexed_chunks(self):
        return self._chunks


class _TornRepoLibrary(_RepoLibrary):
    def __init__(self, repo):
        super().__init__(repo)
        self.torn_snapshot_repo = None

    def snapshot(self):
        snapshot = super().snapshot()
        if self.torn_snapshot_repo is None:
            return snapshot
        from demo.library import _CorpusSnapshot
        return _CorpusSnapshot(
            snapshot.pipeline,
            snapshot.provider,
            self.torn_snapshot_repo,
            snapshot.commit,
            snapshot.generation,
            snapshot.fingerprint,
            snapshot.indexing,
        )


def _candidate(**overrides):
    body = {
        "repo": PRIVATE,
        "session_id": "claude-session-123",
        "decision": "Use SQLite for the local project index",
        "rationale": "It keeps the first version local and operationally simple.",
        "alternatives": [
            {
                "decision": "Use Postgres",
                "rationale": "It improves concurrency but adds an operated service.",
            },
            {
                "decision": "Use JSON files",
                "rationale": "It is initially simple but weak for atomic updates.",
            },
        ],
        "affected_paths": ["demo/index.py"],
    }
    body.update(overrides)
    return body


class AgentModeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.decisions = DecisionLedger(Path(self.tmp.name) / "decisions")
        self.sessions = AgentSessionStore(ttl=600)
        self.writer = _DecisionWriter()
        self.lib = _TornRepoLibrary(PRIVATE)
        self.fx = _ServerFixture(
            self.lib,
            require_auth=True,
            verifier=StaticTokenVerifier({GITHUB_TOKEN: IDENTITY}),
            access_verifier=_StubAccess([(PRIVATE, GITHUB_TOKEN)]),
            default_repo=REPO,
            agent_sessions=self.sessions,
            agent_repo_info=lambda repo, token: (
                {"private": True}
                if repo == PRIVATE and token == GITHUB_TOKEN else None
            ),
            decisions=self.decisions,
            memory_writer=self.writer,
        )
        self.addCleanup(self.fx.close)
        _status, issued = self._post(
            "/auth/agent/session", {}, GITHUB_TOKEN,
        )
        self.agent_token = issued["token"]

    def _request(self, path, token, body=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        return urllib.request.Request(self.fx.base + path, data=data, headers=headers)

    def _post(self, path, body, token):
        with urllib.request.urlopen(self._request(path, token, body)) as response:
            return response.status, json.loads(response.read())

    def _get(self, path, token):
        with urllib.request.urlopen(self._request(path, token)) as response:
            return response.status, json.loads(response.read())

    def test_agent_submits_one_bounded_candidate_but_cannot_confirm_it(self):
        status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )

        self.assertEqual(status, 201)
        self.assertEqual(submitted["status"], "pending")
        self.assertNotIn("session_id", submitted)
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._post(
                "/agent-mode/confirm",
                {"candidate_id": submitted["id"], "selection": "recommended"},
                self.agent_token,
            )
        self.assertEqual(raised.exception.code, 403)
        raised.exception.close()

    def test_raw_session_fields_are_rejected_and_never_written(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._post(
                "/agent-mode/candidates",
                _candidate(transcript="private raw session"),
                self.agent_token,
            )
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(self.decisions.candidates(PRIVATE), [])

    def test_pending_candidate_is_visible_to_the_app_not_fresh_sessions(self):
        self._post("/agent-mode/candidates", _candidate(), self.agent_token)

        _status, app = self._get("/agent-mode/candidates", GITHUB_TOKEN)
        _status, context = self._get("/agent-mode/context", self.agent_token)

        self.assertEqual(app["repo"], PRIVATE)
        self.assertEqual(len(app["candidates"]), 1)
        self.assertEqual(
            context,
            {"repo": PRIVATE, "commit": self.lib.provenance()[1], "decisions": []},
        )

    def test_fresh_session_context_refuses_a_repo_switch_race(self):
        self.lib.torn_snapshot_repo = "other/private-project"

        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._get("/agent-mode/context", self.agent_token)

        self.assertEqual(raised.exception.code, 403)
        raised.exception.close()

    def test_confirmation_creates_reviewed_proposal_then_enters_context(self):
        _status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )

        status, confirmed = self._post(
            "/agent-mode/confirm",
            {"candidate_id": submitted["id"], "selection": "recommended"},
            GITHUB_TOKEN,
        )
        _status, context = self._get("/agent-mode/context", self.agent_token)

        self.assertEqual(status, 201)
        self.assertEqual(confirmed["status"], "confirmed_proposal")
        self.assertEqual(len(self.writer.calls), 1)
        self.assertEqual(self.writer.calls[0]["token"], GITHUB_TOKEN)
        self.assertEqual(context["decisions"][0]["decision"], _candidate()["decision"])
        self.assertEqual(
            context["decisions"][0]["status"],
            "human_confirmed_proposal_not_indexed",
        )
        self.assertEqual(
            context["decisions"][0]["pull_request_url"],
            "https://github.com/acme/agent-project/pull/42",
        )

    def test_merged_and_reindexed_decision_is_injected_as_cited_truth(self):
        _status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )
        _status, confirmed = self._post(
            "/agent-mode/confirm",
            {"candidate_id": submitted["id"], "selection": "recommended"},
            GITHUB_TOKEN,
        )
        path = confirmed["proposal"]["path"]
        text = (
            f"<!-- icarus-agent-mode-decision:v1 id={submitted['id']} -->\n"
            "## Decision\n\nUse SQLite for the local project index\n\n"
            "## Confirmed rationale\n\nKeeps it local.\n\n"
            "## Affected paths\n\n- `demo/index.py`\n"
        )
        self.lib._pipe = _IndexedDecisionPipeline([
            Chunk(ref=f"doc:{path}", source="doc", text=text),
        ])

        _status, context = self._get("/agent-mode/context", self.agent_token)

        projected = context["decisions"][0]
        self.assertEqual(projected["status"], "human_confirmed_merged")
        self.assertEqual(projected["citation_ref"], f"doc:{path}")
        self.assertIn(self.lib.provenance()[1], projected["citation_url"])
        self.assertNotIn("pull_request_url", projected)

    def test_confirmation_retry_returns_existing_state_without_second_github_write(self):
        _status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )
        body = {"candidate_id": submitted["id"], "selection": "recommended"}

        first_status, first = self._post("/agent-mode/confirm", body, GITHUB_TOKEN)
        second_status, second = self._post("/agent-mode/confirm", body, GITHUB_TOKEN)

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 200)
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["proposal"], first["proposal"])
        self.assertEqual(len(self.writer.calls), 1)

    def test_not_sure_neither_calls_github_nor_enters_context(self):
        _status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )

        status, deferred = self._post(
            "/agent-mode/confirm",
            {"candidate_id": submitted["id"], "selection": "not_sure"},
            GITHUB_TOKEN,
        )
        _status, context = self._get("/agent-mode/context", self.agent_token)

        self.assertEqual(status, 200)
        self.assertEqual(deferred["status"], "not_sure")
        self.assertEqual(self.writer.calls, [])
        self.assertEqual(context["decisions"], [])

    def test_other_does_not_inherit_agent_rationale(self):
        _status, submitted = self._post(
            "/agent-mode/candidates", _candidate(), self.agent_token,
        )
        other = "Keep the in-memory index until persistence is justified."

        self._post(
            "/agent-mode/confirm",
            {
                "candidate_id": submitted["id"],
                "selection": "other",
                "other_text": other,
            },
            GITHUB_TOKEN,
        )

        self.assertEqual(self.writer.calls[0]["decision"], other)
        self.assertIsNone(self.writer.calls[0]["rationale"])

    def test_no_decision_acknowledgement_is_not_persisted(self):
        status, body = self._post(
            "/agent-mode/no-decision",
            {"repo": PRIVATE, "session_id": "claude-session-123"},
            self.agent_token,
        )

        self.assertEqual(status, 200)
        self.assertEqual(body, {"repo": PRIVATE, "recorded": False})
        self.assertEqual(list((Path(self.tmp.name) / "decisions").glob("*")), [])

    def test_capture_loop_metrics_distinguish_submission_absence_and_resolution(self):
        with unittest.mock.patch("demo.server.posthog_capture.capture") as capture:
            _status, submitted = self._post(
                "/agent-mode/candidates", _candidate(), self.agent_token,
            )
            self._post(
                "/agent-mode/no-decision",
                {"repo": PRIVATE, "session_id": "another-session"},
                self.agent_token,
            )
            self._post(
                "/agent-mode/confirm",
                {"candidate_id": submitted["id"], "selection": "recommended"},
                GITHUB_TOKEN,
            )

        calls = [(call.args[0], call.args[2]) for call in capture.call_args_list]
        self.assertEqual(
            [name for name, _properties in calls],
            [
                "decision_candidate_submitted",
                "agent_turn_no_decision",
                "decision_candidate_resolved",
            ],
        )
        self.assertEqual(calls[2][1]["selection"], "recommended")
        serialized = json.dumps(calls)
        for private_content in (
            PRIVATE,
            _candidate()["decision"],
            _candidate()["rationale"],
            "claude-session-123",
        ):
            self.assertNotIn(private_content, serialized)


if __name__ == "__main__":
    unittest.main()
