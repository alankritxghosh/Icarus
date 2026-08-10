import json
import subprocess
import unittest
import urllib.request
from unittest.mock import patch

from . import mcp_server


REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"


class McpProtocolTests(unittest.TestCase):
    def test_initialize_echoes_the_client_protocol_and_advertises_tools(self):
        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        })

        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", response["result"]["capabilities"])
        self.assertIn("before planning", response["result"]["instructions"].lower())

    def test_tool_contract_is_read_only_and_repo_explicit(self):
        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        tools = {tool["name"]: tool for tool in response["result"]["tools"]}

        self.assertEqual(
            set(tools),
            {"get_change_context", "explain_code_context", "get_task_context"},
        )
        self.assertTrue(tools["get_change_context"]["annotations"]["readOnlyHint"])
        self.assertTrue(tools["get_task_context"]["annotations"]["readOnlyHint"])
        self.assertIn(
            "repo",
            tools["get_change_context"]["inputSchema"]["required"],
        )
        self.assertIn(
            "repo",
            tools["explain_code_context"]["inputSchema"]["required"],
        )
        self.assertIn(
            "repo",
            tools["get_task_context"]["inputSchema"]["required"],
        )

    def test_notifications_do_not_receive_a_json_rpc_response(self):
        self.assertIsNone(mcp_server.handle_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }))


class McpToolTests(unittest.TestCase):
    @patch("demo.mcp_server._request")
    def test_change_context_opts_into_evidence_and_preserves_honest_unknown(
            self, request):
        request.side_effect = [
            {
                "repo": REPO,
                "commit": COMMIT,
                "state": "ready",
                "private": False,
            },
            {
                "repo": REPO,
                "commit": COMMIT,
                "verdict": "unknown",
                "answer": "",
                "citations": [],
                "evidence": [
                    {
                        "ref": "issue:112",
                        "url": f"https://github.com/{REPO}/issues/112",
                        "excerpt": "Retry support is still requested.",
                    }
                ],
            },
            {
                "repo": REPO,
                "commit": COMMIT,
                "state": "ready",
                "private": False,
            },
        ]

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_change_context",
                "arguments": {
                    "repo": REPO,
                    "question": "Why is there no retry?",
                },
            },
        })

        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["verdict"], "unknown")
        self.assertEqual(
            result["structuredContent"]["evidence"][0]["ref"],
            "issue:112",
        )
        self.assertEqual(
            json.loads(result["content"][0]["text"]),
            result["structuredContent"],
        )
        request.assert_any_call(
            "/ask",
            {
                "question": "Why is there no retry?",
                "include_evidence": True,
                # The agent interface always asks for the per-sentence
                # self-report: a coding agent acts on this answer and needs to
                # know which sentences merge several sources.
                "per_claim": True,
            },
        )

    @patch("demo.mcp_server._request")
    def test_task_context_returns_the_structured_shape(self, request):
        request.side_effect = [
            {"repo": REPO, "commit": COMMIT, "state": "ready", "private": False},
            {
                "repo": REPO, "commit": COMMIT, "indexing": False,
                "task": "implement rate limiting",
                "architecture": [], "dependencies": {"file_edges": [], "package_edges": []},
                "files": ["llm/cli.py"], "decisions": [], "prs": ["pr:400"],
                "issues": [], "risks": [], "constraints": [], "unknowns": [],
                "citations": ["pr:400"],
            },
            {"repo": REPO, "commit": COMMIT, "state": "ready", "private": False},
        ]

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_task_context",
                "arguments": {"repo": REPO, "task": "implement rate limiting"},
            },
        })

        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["task"], "implement rate limiting")
        self.assertEqual(result["structuredContent"]["prs"], ["pr:400"])
        # Not the /ask shape -- no verdict/answer key leaks through.
        self.assertNotIn("verdict", result["structuredContent"])
        request.assert_any_call("/context", {"task": "implement rate limiting"})

    @patch("demo.mcp_server._request")
    def test_repo_mismatch_refuses_before_asking_or_switching(self, request):
        request.return_value = {
            "repo": "octocat/hello",
            "commit": "abc123",
            "state": "ready",
            "private": False,
        }

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_change_context",
                "arguments": {
                    "repo": REPO,
                    "question": "Why is there no retry?",
                },
            },
        })

        self.assertTrue(response["result"]["isError"])
        self.assertIn("octocat/hello", response["result"]["content"][0]["text"])
        request.assert_called_once_with("/status")

    @patch("demo.mcp_server._request")
    def test_code_explanation_sends_an_explicit_selection(self, request):
        request.side_effect = [
            {
                "repo": REPO,
                "commit": COMMIT,
                "state": "ready",
                "private": False,
            },
            {
                "repo": REPO,
                "commit": COMMIT,
                "verdict": "answer",
                "answer": "Because the caller requires UTC.",
                "citations": [],
                "evidence": [],
            },
            {
                "repo": REPO,
                "commit": COMMIT,
                "state": "ready",
                "private": False,
            },
        ]

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "explain_code_context",
                "arguments": {
                    "repo": REPO,
                    "path": "llm/tools.py",
                    "start": 15,
                    "end": 20,
                    "question": "Why UTC?",
                },
            },
        })

        self.assertFalse(response["result"]["isError"])
        self.assertEqual(
            request.call_args_list,
            [
                unittest.mock.call("/status"),
                unittest.mock.call(
                    "/explain",
                    {
                        "repo": REPO,
                        "path": "llm/tools.py",
                        "start": 15,
                        "end": 20,
                        "question": "Why UTC?",
                        "include_evidence": True,
                        "per_claim": True,
                    },
                ),
                unittest.mock.call("/status"),
            ],
        )

    @patch("demo.mcp_server._request")
    def test_private_repo_is_served_like_any_other(self, request):
        """Private repositories ARE answered over MCP (decided 2026-08-07).

        The privacy flag no longer gates this boundary: Icarus cannot verify
        what an MCP client does with tool output, so the exposure is owned by
        whoever configures that client, not refused on their behalf. This test
        exists so the reversal is deliberate -- reinstating a private-repo
        block must break a named test, not silently pass.
        """
        request.side_effect = [
            {
                "repo": "acme/private",
                "commit": "abc123",
                "state": "ready",
                "private": True,
            },
            {
                "repo": "acme/private",
                "commit": "abc123",
                "verdict": "answer",
                "answer": "The constraint exists because of a 2024 incident.",
                "citations": [{"ref": "pr:12", "url": None, "excerpt": ""}],
                "evidence": [
                    {"ref": "code:internal.py", "url": None, "excerpt": "private"}
                ],
            },
            {
                "repo": "acme/private",
                "commit": "abc123",
                "state": "ready",
                "private": True,
            },
        ]

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_change_context",
                "arguments": {
                    "repo": "acme/private",
                    "question": "Why does this constraint exist?",
                },
            },
        })

        self.assertFalse(response["result"]["isError"])
        self.assertIn(
            "2024 incident",
            response["result"]["content"][0]["text"],
        )

    @patch("demo.mcp_server._request")
    def test_repo_switch_during_answer_still_refuses(self, request):
        """Privacy no longer gates, but a repo SWITCH mid-answer still does.

        The payload must describe the repository the caller asked about; a
        corpus swap between preflight and answer is a different question being
        answered, regardless of either repo's privacy.
        """
        request.side_effect = [
            {
                "repo": REPO,
                "commit": COMMIT,
                "state": "ready",
                "private": False,
            },
            {
                "repo": "someone/else",
                "commit": COMMIT,
                "verdict": "unknown",
                "answer": "",
                "citations": [],
                "evidence": [
                    {
                        "ref": "code:secret.py",
                        "url": None,
                        "excerpt": "must not reach the coding model",
                    }
                ],
            },
        ]

        response = mcp_server.handle_message({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "get_change_context",
                "arguments": {
                    "repo": REPO,
                    "question": "Why does this constraint exist?",
                },
            },
        })

        self.assertTrue(response["result"]["isError"])
        self.assertNotIn(
            "must not reach the coding model",
            response["result"]["content"][0]["text"],
        )


class TransportSecurityTests(unittest.TestCase):
    def test_redirects_are_refused_before_authorization_can_be_forwarded(self):
        original = urllib.request.Request(
            "https://brain.example/ask",
            headers={"Authorization": "Bearer never-forward-me"},
        )
        redirected = mcp_server._NoRedirects().redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "https://attacker.example/collect",
        )
        self.assertIsNone(redirected)

    @patch("demo.mcp_server._OPENER.open")
    def test_brain_url_cannot_embed_credentials(self, open_request):
        with patch.dict(
                "os.environ",
                {"ICARUS_BRAIN_URL": "https://user:secret@brain.example"},
                clear=False):
            with self.assertRaises(mcp_server._ToolError):
                mcp_server._request("/status")
        open_request.assert_not_called()


class AutomaticAppSessionTests(unittest.TestCase):
    def tearDown(self):
        mcp_server._cached_agent_session = None

    @patch("demo.mcp_server.time.time", return_value=1_000.0)
    @patch("demo.mcp_server.subprocess.run")
    @patch("demo.mcp_server._app_binary", return_value="/Applications/Icarus.app/Contents/MacOS/Icarus")
    def test_default_connection_asks_the_app_for_a_short_session(
            self, app_binary, run, _clock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "brain_url": "https://brain.example",
                "token": "short-lived",
                "expires_at": 1_600.0,
                "repo": REPO,
            }),
            stderr="",
        )

        with patch.dict("os.environ", {}, clear=True):
            connection = mcp_server._connection()

        self.assertEqual(connection.base, "https://brain.example")
        self.assertEqual(connection.token, "short-lived")
        self.assertTrue(connection.managed)
        run.assert_called_once_with(
            [
                "/Applications/Icarus.app/Contents/MacOS/Icarus",
                "--agent-session",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    @patch("demo.mcp_server.subprocess.run")
    @patch("demo.mcp_server._app_binary")
    def test_explicit_development_configuration_does_not_launch_the_app(
            self, app_binary, run):
        with patch.dict(
                "os.environ",
                {
                    "ICARUS_BRAIN_URL": "http://127.0.0.1:9000",
                    "ICARUS_TOKEN": "dev-token",
                },
                clear=True):
            connection = mcp_server._connection()

        self.assertEqual(connection.base, "http://127.0.0.1:9000")
        self.assertEqual(connection.token, "dev-token")
        self.assertFalse(connection.managed)
        app_binary.assert_not_called()
        run.assert_not_called()

    @patch("demo.mcp_server.time.time", return_value=1_000.0)
    @patch("demo.mcp_server.subprocess.run")
    @patch("demo.mcp_server._app_binary", return_value="/Applications/Icarus.app/Contents/MacOS/Icarus")
    def test_invalid_app_output_fails_before_any_brain_request(
            self, _app_binary, run, _clock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"brain_url":"https://brain.example","token":"secret"}',
            stderr="",
        )

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(mcp_server._ToolError) as raised:
                mcp_server._connection()

        self.assertIn("valid agent session", str(raised.exception))

    @patch("demo.mcp_server.time.time", return_value=1_000.0)
    @patch("demo.mcp_server.subprocess.run")
    @patch("demo.mcp_server._app_binary", return_value="/Applications/Icarus.app/Contents/MacOS/Icarus")
    def test_unexpired_session_is_reused_without_persisting_or_relaunching(
            self, _app_binary, run, _clock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "brain_url": "https://brain.example",
                "token": "short-lived",
                "expires_at": 1_600.0,
                "repo": REPO,
            }),
            stderr="",
        )

        with patch.dict("os.environ", {}, clear=True):
            first = mcp_server._connection()
            second = mcp_server._connection()

        self.assertIs(first, second)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
