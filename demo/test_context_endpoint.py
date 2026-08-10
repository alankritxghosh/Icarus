# demo/test_context_endpoint.py
"""POST /context at the real HTTP boundary -- Experiment B's `icarus.context
(task)` (docs/HANDOFF.md's Agent Mode entry).

Reuses `test_investigate_endpoint`'s exact harness (same chunks, same
ScriptedWriter, same stub Library) rather than duplicating it: /context runs
the identical investigate()/conclude() engine /investigate does, so the same
fixture proves both. What's tested here is specific to the NEW shape: no
`investigation` wrapper key, a flat structured schema, no conversation state
(no `fresh`, no subject inheritance -- deliberately stateless, see the
handler's own docstring), and its own entitlement/rate-limit gates.
"""
import threading
import unittest
import urllib.error
from http.server import HTTPServer
from pathlib import Path
import tempfile

from evals.entities import build_entity_index
from .auth import StaticTokenVerifier
from .ratelimit import RateLimiter
from .server import make_handler
from .test_server import _StubRegistry
from .test_investigate_endpoint import CHUNKS, COMMIT, REPO, ScriptedWriter, _Library, _post


class ContextEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        html = Path(cls._tmp.name) / "index.html"
        html.write_text("<html></html>")
        cls.writer = ScriptedWriter()
        cls.lib = _Library(cls.writer)
        handler = make_handler(
            _StubRegistry(cls.lib), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "user-a", "tok-b": "user-b"}),
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60),
            investigate_limiter=RateLimiter(100, 60))
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def ctx(self, task, token="tok-a"):
        return _post(self.base + "/context", {"task": task}, token=token)

    def test_returns_the_documented_flat_schema(self):
        status, payload = self.ctx("understand PR #400's chunking change")
        self.assertEqual(status, 200)
        for key in ("repo", "commit", "indexing", "task", "architecture",
                   "dependencies", "files", "decisions", "prs", "issues",
                   "risks", "constraints", "unknowns", "citations"):
            self.assertIn(key, payload)
        self.assertEqual(payload["repo"], REPO)
        self.assertEqual(payload["commit"], COMMIT)

    def test_is_not_shaped_like_ask_or_investigate(self):
        """No verdict/answer/investigation wrapper -- this is a structured
        package, not a conversational answer (the handler's own docstring)."""
        _, payload = self.ctx("understand PR #400's chunking change")
        self.assertNotIn("verdict", payload)
        self.assertNotIn("answer", payload)
        self.assertNotIn("investigation", payload)

    def test_task_echoes_what_was_asked(self):
        _, payload = self.ctx("understand PR #400's chunking change")
        self.assertEqual(payload["task"], "understand PR #400's chunking change")

    def test_gathered_pr_is_reported_even_though_it_is_not_a_conversation(self):
        _, payload = self.ctx("talk to me about PR #400")
        self.assertIn("pr:400", payload["prs"])
        self.assertIn("issue:372", payload["issues"])

    def test_citations_are_grounded_in_what_the_gate_actually_verified(self):
        _, payload = self.ctx("talk to me about PR #400")
        self.assertEqual(payload["citations"], ["pr:400"])

    def test_dependencies_key_is_structures_own_shape(self):
        _, payload = self.ctx("talk to me about PR #400")
        self.assertIn("file_edges", payload["dependencies"])
        self.assertIn("package_edges", payload["dependencies"])

    def test_missing_task_is_a_clean_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/context", {}, token="tok-a")
        self.assertEqual(cm.exception.code, 400)

    def test_blank_task_is_a_clean_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/context", {"task": "   "}, token="tok-a")
        self.assertEqual(cm.exception.code, 400)

    def test_unauthenticated_caller_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/context", {"task": "x"})
        self.assertEqual(cm.exception.code, 401)

    def test_rate_limit_is_enforced_like_investigate(self):
        """/context spends the same several-writer-call budget /investigate
        does, so it must be gated by the SAME tight limiter category, not by
        the cheap single-call /ask budget."""
        html = Path(self._tmp.name) / "index2.html"
        html.write_text("<html></html>")
        tight = RateLimiter(1, 60)
        handler = make_handler(
            _StubRegistry(self.lib), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"tok-c": "user-c"}),
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60), investigate_limiter=tight)
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            status1, _ = _post(base + "/context", {"task": "x"}, token="tok-c")
            self.assertEqual(status1, 200)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(base + "/context", {"task": "y"}, token="tok-c")
            self.assertEqual(cm.exception.code, 429)
        finally:
            server.shutdown()
            server.server_close()


class AgentSessionContextTests(unittest.TestCase):
    """A coding agent's default auth path (demo/mcp_server.py's docstring: a
    ten-minute credential minted by the installed app) must actually reach
    /context. Regression guard for a real bug found deploying this feature:
    the agent-session route whitelist (server.py's do_POST) was never updated
    when /context was added, so `get_task_context`'s default auth path was
    silently 403ing with 'agent sessions are read-only and route-scoped'."""

    @classmethod
    def setUpClass(cls):
        from .agent_sessions import AgentSessionStore

        cls._tmp = tempfile.TemporaryDirectory()
        html = Path(cls._tmp.name) / "index.html"
        html.write_text("<html></html>")
        cls.writer = ScriptedWriter()
        cls.lib = _Library(cls.writer)
        cls.sessions = AgentSessionStore(ttl=600.0)

        def repo_info(repo, token):
            return {"private": False} if repo == REPO else None

        handler = make_handler(
            _StubRegistry(cls.lib), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"gh-tok": "user-a"}),
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60), investigate_limiter=RateLimiter(100, 60),
            agent_sessions=cls.sessions, agent_repo_info=repo_info)
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def test_agent_session_can_call_context(self):
        _, issued = _post(self.base + "/auth/agent/session", {}, token="gh-tok")
        agent_token = issued["token"]

        status, payload = _post(self.base + "/context",
                                {"task": "understand PR #400"}, token=agent_token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["task"], "understand PR #400")
        self.assertIn("pr:400", payload["prs"])


if __name__ == "__main__":
    unittest.main()
