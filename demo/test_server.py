# demo/test_server.py
import json
import tempfile
import threading
import unittest
import unittest.mock
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path

from evals.pipeline import Result, Pipeline
from .server import make_handler

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"


class _StubPipeline(Pipeline):
    """Answers a known question, abstains on anything else -- no network."""

    def answer(self, question, token=None):
        if "responses api" in question.lower():
            return Result(verdict="answer", answer="Because other plugins import the old class.",
                          citations=["pr:1435"], retrieved=["pr:1435", "code:llm/x.py"])
        return Result(verdict="unknown", retrieved=["code:llm/x.py", "code:llm/y.py"])

    def explain(self, path, start, end, question=None):
        """Brick D: a line-covered location answers; anywhere else abstains --
        mirrors GatedPipeline.explain's real "no coverage -> honest unknown"
        contract, not a special-cased error, from a fixed known location."""
        self.last_explain_call = (path, start, end, question)
        if path == "llm/tools.py" and start <= 20 <= end:
            return Result(verdict="answer", answer="It returns the current time.",
                          citations=["code:llm/tools.py#L10-L40"],
                          retrieved=["code:llm/tools.py#L10-L40", "pr:99"])
        return Result(verdict="unknown", retrieved=["code:llm/tools.py#L10-L40"])


class _StubLibrary:
    """Stand-in for demo.library.Library: fixed pipeline, records connects."""

    def __init__(self):
        self._pipe = _StubPipeline()
        self.connected = []
        self.connect_calls = []
        self.background_upgrades = []  # records the background_upgrade flag per connect
        self.private_calls = []  # records the `private` flag per connect
        self.token_seen = []  # records the token per connect (to assert leak-safe routing)

    def current_pipeline(self):
        return self._pipe

    def provenance(self):
        return (REPO, COMMIT)

    def status_snapshot(self):
        return {"state": "ready", "repo": REPO, "commit": COMMIT,
                "counts": None, "error": None, "phase": None, "private": False}

    def connect_sync(self, repo, token=None, private=False, background_upgrade=False):
        self.connected.append(repo)
        self.connect_calls.append(repo)
        self.background_upgrades.append(background_upgrade)
        self.private_calls.append(private)
        self.token_seen.append(token)
        return self.status_snapshot()  # mirrors the real Library.connect_sync's return


def _post(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.html = Path(cls._tmp.name) / "index.html"
        cls.html.write_text('<html><body><input id="question"></body></html>')
        cls.lib = _StubLibrary()
        handler = make_handler(_StubRegistry(cls.lib), str(cls.html))
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def test_get_root_serves_html(self):
        with urllib.request.urlopen(self.base + "/") as resp:
            body = resp.read().decode()
        self.assertEqual(resp.status, 200)
        self.assertIn('id="question"', body)

    def test_ask_answer(self):
        status, payload = _post(self.base + "/ask", {"question": "Why the Responses API as a new class?"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["verdict"], "answer")
        self.assertEqual(payload["citations"][0]["url"], "https://github.com/simonw/llm/pull/1435")

    def test_ask_unknown(self):
        status, payload = _post(self.base + "/ask", {"question": "What does this code do?"})
        self.assertEqual(payload["verdict"], "unknown")
        self.assertEqual(payload["answer"], "")
        self.assertEqual(payload["searched"], ["code:llm/x.py", "code:llm/y.py"])

    def test_health_reports_ok_and_provenance(self):
        with urllib.request.urlopen(self.base + "/health") as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read())
        self.assertTrue(body["ok"])
        self.assertEqual(body["repo"], REPO)
        self.assertEqual(body["commit"], COMMIT)

    def test_status_reports_active_repo(self):
        with urllib.request.urlopen(self.base + "/status") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(json.loads(resp.read())["repo"], REPO)

    def test_connect_valid_repo_starts_switch(self):
        import time
        status, payload = _post(self.base + "/connect", {"repo": "octocat/hello"})
        self.assertEqual(status, 202)
        self.assertEqual(payload["state"], "indexing")
        for _ in range(50):  # the connect runs in a background thread
            if "octocat/hello" in self.lib.connected:
                break
            time.sleep(0.02)
        self.assertIn("octocat/hello", self.lib.connected)

    def test_connect_bad_repo_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/connect", {"repo": "not-a-repo"})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_ask_missing_question_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/ask", {"nope": "x"})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    # --- Brick D: POST /explain ---

    def test_explain_answer(self):
        status, payload = _post(self.base + "/explain",
                                {"repo": REPO, "path": "llm/tools.py", "start": 15, "end": 20})
        self.assertEqual(status, 200)
        self.assertEqual(payload["verdict"], "answer")
        self.assertEqual(
            payload["citations"][0]["url"],
            f"https://github.com/{REPO}/blob/{COMMIT}/llm/tools.py#L10-L40",
        )

    def test_explain_no_coverage_is_honest_unknown(self):
        # A location the pipeline has no evidence for -- 200 with an honest
        # unknown, not an error (mirrors cite-or-unknown, not a 404/500).
        status, payload = _post(self.base + "/explain",
                                {"repo": REPO, "path": "llm/other.py", "start": 1, "end": 5})
        self.assertEqual(status, 200)
        self.assertEqual(payload["verdict"], "unknown")
        self.assertEqual(payload["answer"], "")

    def test_explain_passes_optional_question_through(self):
        _post(self.base + "/explain",
             {"repo": REPO, "path": "llm/tools.py", "start": 15, "end": 20,
              "question": "why does this return UTC?"})
        self.assertEqual(
            self.lib._pipe.last_explain_call,
            ("llm/tools.py", 15, 20, "why does this return UTC?"),
        )

    def test_explain_without_question_passes_none(self):
        _post(self.base + "/explain", {"repo": REPO, "path": "llm/tools.py", "start": 15, "end": 20})
        self.assertIsNone(self.lib._pipe.last_explain_call[3])

    def test_explain_wrong_repo_refuses_without_calling_pipeline(self):
        # A stale extension tab pointing at a DIFFERENT repo than the one
        # currently connected must refuse, never silently answer about it.
        self.lib._pipe.last_explain_call = None
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain",
                 {"repo": "octocat/hello", "path": "llm/tools.py", "start": 15, "end": 20})
        self.assertEqual(cm.exception.code, 409)
        cm.exception.close()
        self.assertIsNone(self.lib._pipe.last_explain_call)  # never reached the pipeline

    def test_explain_missing_field_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain", {"repo": REPO, "path": "llm/tools.py", "start": 15})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_explain_non_integer_start_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain",
                 {"repo": REPO, "path": "llm/tools.py", "start": "fifteen", "end": 20})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_explain_end_before_start_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain", {"repo": REPO, "path": "llm/tools.py", "start": 20, "end": 15})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_explain_non_positive_start_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain", {"repo": REPO, "path": "llm/tools.py", "start": 0, "end": 5})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_explain_blank_path_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/explain", {"repo": REPO, "path": "  ", "start": 1, "end": 5})
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(self.base + "/nope")
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()


class ResolveProvenanceTests(unittest.TestCase):
    """The demo's repo/commit come from corpus meta.json when present, else fall
    back to the labelled set's corpus block (back-compat)."""

    def test_meta_wins_when_present(self):
        from .server import resolve_provenance
        with tempfile.TemporaryDirectory() as d:
            meta = Path(d) / "meta.json"
            meta.write_text(json.dumps({"repo": "octocat/hello", "commit": "abc123"}))
            q = Path(d) / "q.json"
            q.write_text(json.dumps({"corpus": {"repo": "simonw/llm", "commit": "zzz"}}))
            self.assertEqual(resolve_provenance(meta, q), ("octocat/hello", "abc123"))

    def test_falls_back_to_questions_when_no_meta(self):
        from .server import resolve_provenance
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "q.json"
            q.write_text(json.dumps({"corpus": {"repo": "simonw/llm", "commit": "zzz"}}))
            self.assertEqual(resolve_provenance(Path(d) / "missing.json", q), ("simonw/llm", "zzz"))


class IndexHtmlSmokeTests(unittest.TestCase):
    """The served page must keep the hooks the front-end contract depends on."""

    def setUp(self):
        self.html = (Path(__file__).resolve().parent / "index.html").read_text()

    def test_has_question_input_and_ask_button(self):
        self.assertIn('id="question"', self.html)
        self.assertIn('id="ask"', self.html)

    def test_has_github_sign_in(self):
        self.assertIn("Sign in with GitHub", self.html)
        self.assertIn("/auth/github/begin", self.html)

    def test_posts_to_ask_and_handles_both_verdicts(self):
        self.assertIn("/ask", self.html)
        self.assertIn('verdict', self.html)

    def test_renders_the_honest_unknown_hero(self):
        self.assertIn("No one wrote this down", self.html)

    def test_has_repo_connect_controls(self):
        self.assertIn('id="repo"', self.html)
        self.assertIn("/connect", self.html)
        self.assertIn("/status", self.html)

    def test_no_hardcoded_fake_recent_questions(self):
        self.assertNotIn("mock service requests with MSW", self.html)
        self.assertNotIn("legacy adapter", self.html)

    def test_no_dead_placeholder_nav_links(self):
        self.assertNotIn('href="#"', self.html)


class _StubRegistry:
    """Stand-in for demo.registry.LibraryRegistry: one library for everyone,
    records which identities asked."""

    def __init__(self, lib):
        self.lib = lib
        self.seen = []
        self.disconnected = []

    def library_for(self, user_id):
        self.seen.append(user_id)
        return self.lib

    def disconnect(self, user_id):
        self.disconnected.append(user_id)


class _ServerFixture:
    """Spin up a real server on a random port with the given handler kwargs."""

    def __init__(self, lib, **handler_kwargs):
        registry = lib if hasattr(lib, "library_for") else _StubRegistry(lib)
        self._tmp = tempfile.TemporaryDirectory()
        html = Path(self._tmp.name) / "index.html"
        html.write_text("<html></html>")
        handler = make_handler(registry, str(html), **handler_kwargs)
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_port
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()


class MalformedContentLengthTests(unittest.TestCase):
    """Security M1: a negative or non-integer Content-Length must be rejected
    with a prompt HTTP error, never read into a blocking `rfile.read(-1)` that
    holds a server thread open. Uses a raw socket because urllib computes a
    correct Content-Length for you (you can't send a malformed one through it)."""

    def _raw_post(self, port, content_length_header):
        import socket
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            s.sendall(
                b"POST /ask HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {content_length_header}\r\n".encode()
                + b"\r\n"
            )
            s.settimeout(5)  # if the server hangs on read(-1), this raises instead of blocking forever
            return s.recv(2048)
        finally:
            s.close()

    def test_negative_content_length_is_rejected_not_hung(self):
        fx = _ServerFixture(_StubLibrary())
        try:
            resp = self._raw_post(fx.port, "-1")
        finally:
            fx.close()
        self.assertTrue(resp.startswith(b"HTTP/"), "server must answer, not hang")
        status = int(resp.split()[1])
        self.assertIn(status, (400, 413))

    def test_non_integer_content_length_is_rejected_not_a_dropped_connection(self):
        fx = _ServerFixture(_StubLibrary())
        try:
            resp = self._raw_post(fx.port, "notanumber")
        finally:
            fx.close()
        self.assertTrue(resp.startswith(b"HTTP/"), "server must answer, not drop the connection")
        status = int(resp.split()[1])
        self.assertIn(status, (400, 413))


class OriginGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = _ServerFixture(_StubLibrary())
        cls.base = cls.fx.base

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def test_forged_host_is_rejected(self):
        req = urllib.request.Request(self.base + "/status")
        req.add_header("Host", "evil.example.com")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        cm.exception.close()

    def test_cross_origin_post_is_rejected(self):
        data = json.dumps({"question": "hi"}).encode()
        req = urllib.request.Request(self.base + "/ask", data=data,
                                     headers={"Content-Type": "application/json",
                                              "Origin": "https://evil.example.com"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        cm.exception.close()

    def test_loopback_host_is_allowed(self):
        with urllib.request.urlopen(self.base + "/status") as resp:
            self.assertEqual(resp.status, 200)


class ResolveStorageRootTests(unittest.TestCase):
    """ICARUS_STORAGE_ROOT falls back to the default when unset AND when set
    but blank (a PaaS env-var UI can easily leave a value blank) -- either way
    it must never silently resolve to the cwd."""

    def test_unset_and_blank_both_fall_back_to_default(self):
        from pathlib import Path
        from .server import _resolve_storage_root
        default = Path("/tmp/icarus-default-data")
        self.assertEqual(_resolve_storage_root(None, default), default)
        self.assertEqual(_resolve_storage_root("", default), default)

    def test_explicit_value_is_honored(self):
        from pathlib import Path
        from .server import _resolve_storage_root
        default = Path("/tmp/icarus-default-data")
        self.assertEqual(_resolve_storage_root("/mnt/data", default), Path("/mnt/data"))


class AllowedHostsTests(unittest.TestCase):
    """The Host guard is configurable for cloud hosting: a named host is allowed,
    a foreign one is still 403, and '*' (cloud mode) accepts any Host/Origin."""

    def test_parse_allowed_hosts(self):
        from .server import _parse_allowed_hosts
        self.assertIsNone(_parse_allowed_hosts(None))
        self.assertIsNone(_parse_allowed_hosts(""))
        self.assertIsNone(_parse_allowed_hosts("  ,  "))
        self.assertEqual(_parse_allowed_hosts("a.example.com"), {"a.example.com"})
        self.assertEqual(_parse_allowed_hosts("a.com, b.com"), {"a.com", "b.com"})
        self.assertEqual(_parse_allowed_hosts("*"), {"*"})

    def test_named_host_allowed_foreign_rejected(self):
        fx = _ServerFixture(_StubLibrary(), allowed_hosts={"brain.example.com"})
        try:
            ok = urllib.request.Request(fx.base + "/status")
            ok.add_header("Host", "brain.example.com")
            with urllib.request.urlopen(ok) as resp:
                self.assertEqual(resp.status, 200)

            bad = urllib.request.Request(fx.base + "/status")
            bad.add_header("Host", "evil.example.com")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(bad)
            self.assertEqual(cm.exception.code, 403)
            cm.exception.close()
        finally:
            fx.close()

    def test_wildcard_accepts_any_host_and_origin(self):
        fx = _ServerFixture(_StubLibrary(), allowed_hosts={"*"})
        try:
            # Any Host passes.
            req = urllib.request.Request(fx.base + "/status")
            req.add_header("Host", "icarus-xyz.onrender.com")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
            # A cross-origin POST passes too — the bearer gate, not Origin, is the
            # boundary in cloud mode (here auth is off, so it just answers).
            data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
            post = urllib.request.Request(fx.base + "/ask", data=data,
                                          headers={"Content-Type": "application/json",
                                                   "Origin": "https://anywhere.example.com"})
            with urllib.request.urlopen(post) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            fx.close()


class BodyCapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = _ServerFixture(_StubLibrary())
        cls.base = cls.fx.base

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def test_oversized_body_is_rejected(self):
        big = json.dumps({"question": "x" * 200_000}).encode()
        req = urllib.request.Request(self.base + "/ask", data=big,
                                     headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            resp.close()
            self.fail("server accepted an oversized body")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 413)  # the clean rejection
            e.close()
        except (urllib.error.URLError, ConnectionError):
            # Also a valid rejection, and a real race under load: the server
            # sends its 413 and closes the socket before the client finishes
            # streaming the 200KB body, so urllib surfaces the connection reset
            # instead of reading the response. Either way the body never got in.
            pass


class ConcurrencyTests(unittest.TestCase):
    """A slow request must not block a second concurrent request."""

    def test_slow_request_does_not_block_a_fast_one(self):
        import time
        from http.server import ThreadingHTTPServer

        release = threading.Event()

        class _SlowLibrary(_StubLibrary):
            def status_snapshot(self):
                release.wait(timeout=5)
                return super().status_snapshot()

        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "index.html"
            html.write_text("<html></html>")
            # make_handler needs a REGISTRY (exposing library_for), not a bare
            # Library -- wrap it, or /status errors instead of running slowly and
            # the concurrency assertion proves nothing.
            handler = make_handler(_StubRegistry(_SlowLibrary()), str(html))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = server.server_port
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            slow_result = {}

            def _do_slow():
                try:
                    with urllib.request.urlopen(base + "/status", timeout=5) as r:
                        slow_result["code"] = r.status
                except Exception as e:  # capture -- an in-thread crash must fail the test
                    slow_result["error"] = repr(e)

            slow = threading.Thread(target=_do_slow, daemon=True)
            try:
                slow.start()
                time.sleep(0.2)
                start = time.time()
                with urllib.request.urlopen(base + "/", timeout=3) as resp:
                    self.assertEqual(resp.status, 200)
                self.assertLess(time.time() - start, 2.0)   # fast one not blocked
            finally:
                release.set()
                slow.join(timeout=5)
                server.shutdown()
                server.server_close()
            # The slow request must have genuinely reached the (blocked) library and
            # then succeeded -- proof it ran concurrently, not that it errored out.
            self.assertEqual(slow_result.get("code"), 200, slow_result)


class AskWriterFailureTests(unittest.TestCase):
    """A writer failure (missing key / provider outage) must return a clean JSON
    503, never drop the connection with no response (Sol P1)."""

    def test_writer_exception_returns_503_json(self):
        from http.server import ThreadingHTTPServer

        class _BoomPipeline:
            def answer(self, q, token=None):
                raise RuntimeError("GEMINI_PAID_API_KEY not set")

        class _BoomLibrary(_StubLibrary):
            def current_pipeline(self):
                return _BoomPipeline()

        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "index.html"
            html.write_text("<html></html>")
            handler = make_handler(_StubRegistry(_BoomLibrary()), str(html))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = server.server_port
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            try:
                data = json.dumps({"question": "why?"}).encode()
                req = urllib.request.Request(base + "/ask", data=data,
                                             headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(req)
                self.assertEqual(ctx.exception.code, 503)
                self.assertIn("error", json.loads(ctx.exception.read()))
            finally:
                server.shutdown()
                server.server_close()


class AuthGateTests(unittest.TestCase):
    """With require_auth, /ask and /connect need a valid GitHub bearer."""

    @classmethod
    def setUpClass(cls):
        from .auth import StaticTokenVerifier
        cls.fx = _ServerFixture(_StubLibrary(), require_auth=True,
                                verifier=StaticTokenVerifier({"good-token"}))
        cls.base = cls.fx.base

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def test_ask_without_token_is_401(self):
        data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
        req = urllib.request.Request(self.base + "/ask", data=data,
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()

    def test_ask_with_bad_token_is_401(self):
        data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
        req = urllib.request.Request(self.base + "/ask", data=data,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer wrong"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()

    def test_ask_with_valid_token_succeeds(self):
        data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
        req = urllib.request.Request(self.base + "/ask", data=data,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer good-token"})
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())
        self.assertEqual(resp.status, 200)
        self.assertEqual(payload["verdict"], "answer")

    def test_status_is_open_even_with_auth_required(self):
        # /status must stay pollable so the app can show connection state pre-auth.
        with urllib.request.urlopen(self.base + "/status") as resp:
            self.assertEqual(resp.status, 200)


class GitHubLoginEndpointTests(unittest.TestCase):
    """The web-login endpoints: begin → callback (302 to icarus://) → redeem.
    Offline: the token exchange is faked."""

    @classmethod
    def setUpClass(cls):
        from .github_oauth import OAuthFlow

        def fake_exchange(code, *, client_id, client_secret, redirect_uri):
            return f"tok-{code}"

        cls.flow = OAuthFlow("cid", "secret", "http://127.0.0.1:8000/auth/github/callback",
                             exchanger=fake_exchange)
        cls.fx = _ServerFixture(_StubLibrary(), oauth=cls.flow)
        cls.base, cls.port = cls.fx.base, cls.fx.port

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def _begin(self):
        req = urllib.request.Request(self.base + "/auth/github/begin", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["authorize_url"]

    def _begin_mode(self, mode, redirect_target=None):
        body = {"mode": mode}
        if redirect_target is not None:
            body["redirect_target"] = redirect_target
        req = urllib.request.Request(
            self.base + "/auth/github/begin",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["authorize_url"]

    def test_web_mode_callback_redirects_to_page(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(urlparse(self._begin_mode("web")).query)["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEW&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(loc.startswith("/?session="),
                        f"web login must return to the page, got {loc!r}")

    # --- Brick D: extension mode ---

    _EXT_TARGET = "https://" + "a" * 32 + ".chromiumapp.org/"

    def test_extension_mode_begin_requires_a_redirect_target(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._begin_mode("extension")
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_extension_mode_begin_rejects_a_non_chromiumapp_target(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._begin_mode("extension", redirect_target="https://evil.example.com/")
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_extension_mode_callback_redirects_to_the_chromiumapp_target(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(
            urlparse(self._begin_mode("extension", redirect_target=self._EXT_TARGET)).query
        )["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEX&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(
            loc.startswith(self._EXT_TARGET + "?session="),
            f"extension login must return to its own chromiumapp.org target, got {loc!r}",
        )

    def test_extension_mode_full_flow_redeems_the_real_token(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(
            urlparse(self._begin_mode("extension", redirect_target=self._EXT_TARGET)).query
        )["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEEXT&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        session = parse_qs(urlparse(loc).query)["session"][0]
        req = urllib.request.Request(self.base + "/auth/github/redeem",
                                     data=json.dumps({"session": session}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(json.loads(resp.read())["token"], "tok-CODEEXT")

    def test_app_mode_callback_still_uses_custom_scheme(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(urlparse(self._begin()).query)["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEA&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(loc.startswith("icarus://auth?session="),
                        f"app login must stay on the custom scheme, got {loc!r}")

    def test_begin_returns_github_authorize_url(self):
        url = self._begin()
        self.assertIn("github.com/login/oauth/authorize", url)
        self.assertIn("state=", url)

    def test_full_flow_begin_callback_redeem(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(urlparse(self._begin()).query)["state"][0]

        # Callback: 302 to icarus://auth?session=... (don't follow the custom scheme).
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODE9&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(loc.startswith("icarus://auth?session="))
        session = parse_qs(urlparse(loc).query)["session"][0]

        # Redeem the session id for the token (single-use).
        req = urllib.request.Request(self.base + "/auth/github/redeem",
                                     data=json.dumps({"session": session}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(json.loads(resp.read())["token"], "tok-CODE9")

    def test_redeem_unknown_session_is_404(self):
        req = urllib.request.Request(self.base + "/auth/github/redeem",
                                     data=json.dumps({"session": "nope"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()

    def test_callback_bad_state_is_400(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/auth/github/callback?code=X&state=forged")
        r = conn.getresponse()
        r.read(); conn.close()
        self.assertEqual(r.status, 400)


class IdentityTests(unittest.TestCase):
    """The handler resolves an identity per request: 'local' when auth is off,
    the verified GitHub id when auth is on."""

    def test_identity_is_local_when_auth_off(self):
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg)
        try:
            urllib.request.urlopen(fx.base + "/status").read()
        finally:
            fx.close()
        self.assertEqual(reg.seen, ["local"])

    def test_identity_is_the_github_id_when_auth_on(self):
        from .auth import StaticTokenVerifier
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
            req = urllib.request.Request(fx.base + "/ask", data=data,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer tok-a"})
            urllib.request.urlopen(req).read()
        finally:
            fx.close()
        self.assertIn("1001", reg.seen)


class DisconnectTests(unittest.TestCase):
    def test_disconnect_requires_auth_when_auth_on(self):
        from .auth import StaticTokenVerifier
        fx = _ServerFixture(_StubRegistry(_StubLibrary()), require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(fx.base + "/disconnect", {})
            self.assertEqual(cm.exception.code, 401)
            cm.exception.close()
        finally:
            fx.close()

    def test_disconnect_calls_registry_with_the_callers_identity(self):
        from .auth import StaticTokenVerifier
        reg = _StubRegistry(_StubLibrary())
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            req = urllib.request.Request(
                fx.base + "/disconnect", data=b"{}",
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer tok-a"})
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            fx.close()
        self.assertEqual(reg.disconnected, ["1001"])

    def test_disconnect_surfaces_deletion_failure_as_500(self):
        """Regression test for registry.py's rmtree(ignore_errors=True)
        removal: a genuine on-disk deletion failure must come back as an
        honest JSON error, not an unhandled exception that drops the
        connection with no response at all (found live 2026-07-13: curl got
        HTTP 000 against a real chmod-protected directory)."""
        from .auth import StaticTokenVerifier

        class _FailingRegistry(_StubRegistry):
            def disconnect(self, user_id):
                raise PermissionError("[Errno 13] Permission denied: '/fake/path'")

        reg = _FailingRegistry(_StubLibrary())
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            req = urllib.request.Request(
                fx.base + "/disconnect", data=b"{}",
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer tok-a"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 500)
            body = json.loads(cm.exception.read())
            self.assertIn("error", body)
            cm.exception.close()
        finally:
            fx.close()


class PrivateConnectRouteTests(unittest.TestCase):
    """/connect must verify caller access BEFORE spawning any background work
    when auth is required. A repo the caller CANNOT read is refused (403). A
    PRIVATE repo the caller CAN read is routed as private, cloned with the
    caller's OWN token; a PUBLIC repo is routed public and NEVER handed the
    token. In local dev (auth off) there's no access check at all."""

    def _connect(self, base, token=None, repo="acme/secret"):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(base + "/connect", data=json.dumps({"repo": repo}).encode(),
                                     headers=headers)
        return urllib.request.urlopen(req)

    def test_repo_info_none_is_403_and_never_spawns_connect(self):
        from .auth import StaticTokenVerifier
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg, require_auth=True, verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            with unittest.mock.patch("demo.server.github_access.repo_info", return_value=None) as m:
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._connect(fx.base, token="tok-a")
                self.assertEqual(cm.exception.code, 403)
                cm.exception.close()
                m.assert_called_once()
        finally:
            fx.close()
        import time
        time.sleep(0.05)  # give any (incorrectly) spawned thread a chance to run
        self.assertEqual(lib.connected, [])

    def test_private_repo_routes_as_private_with_the_callers_token(self):
        from .auth import StaticTokenVerifier
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg, require_auth=True, verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            with unittest.mock.patch("demo.server.github_access.repo_info",
                                     return_value={"private": True}):
                status, payload = _post_with_auth(fx.base + "/connect", {"repo": "acme/secret"}, "tok-a")
            self.assertEqual(status, 202)
        finally:
            fx.close()
        import time
        for _ in range(50):
            if lib.connect_calls:
                break
            time.sleep(0.02)
        # Routed as PRIVATE, cloned with the CALLER's own token.
        self.assertEqual(lib.connect_calls, ["acme/secret"])
        self.assertEqual(lib.private_calls, [True])
        self.assertEqual(lib.token_seen, ["tok-a"])

    def test_public_repo_spawns_connect_without_token(self):
        from .auth import StaticTokenVerifier
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg, require_auth=True, verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            with unittest.mock.patch("demo.server.github_access.repo_info",
                                     return_value={"private": False}):
                status, payload = _post_with_auth(fx.base + "/connect", {"repo": "octo/pub"}, "tok-a")
            self.assertEqual(status, 202)
        finally:
            fx.close()
        import time
        for _ in range(50):
            if lib.connect_calls:
                break
            time.sleep(0.02)
        self.assertEqual(lib.connect_calls, ["octo/pub"])
        self.assertEqual(lib.private_calls, [False])
        self.assertEqual(lib.token_seen, [None])  # a PUBLIC repo is never handed the token

    def test_local_dev_auth_off_never_calls_repo_info(self):
        # auth off (today's default) must behave exactly as before: no access
        # check at all. Patch repo_info to raise if it's ever called.
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg)  # require_auth defaults False
        try:
            def _boom(*a, **k):
                raise AssertionError("repo_info must not be called when auth is off")
            with unittest.mock.patch("demo.server.github_access.repo_info", side_effect=_boom):
                status, payload = _post(fx.base + "/connect", {"repo": "octo/pub"})
            self.assertEqual(status, 202)
        finally:
            fx.close()
        import time
        for _ in range(50):
            if lib.connect_calls:
                break
            time.sleep(0.02)
        self.assertEqual(lib.connect_calls, ["octo/pub"])


class RateLimitTests(unittest.TestCase):
    """/ask is rate-limited per identity; the limit is checked before any real
    (billed) work happens, and a different identity is unaffected."""

    def test_second_ask_in_window_is_429(self):
        from .ratelimit import RateLimiter
        fx = _ServerFixture(_StubLibrary(), ask_limiter=RateLimiter(1, 60))
        try:
            status, payload = _post(fx.base + "/ask", {"question": "Why the Responses API as a new class?"})
            self.assertEqual(status, 200)

            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(fx.base + "/ask", {"question": "Why the Responses API as a new class?"})
            self.assertEqual(cm.exception.code, 429)
            cm.exception.close()
        finally:
            fx.close()

    def test_a_different_identity_is_not_rate_limited_by_the_first(self):
        from .auth import StaticTokenVerifier
        from .ratelimit import RateLimiter
        reg = _StubRegistry(_StubLibrary())
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"}),
                            ask_limiter=RateLimiter(1, 60))
        try:
            status, _ = _post_with_auth(fx.base + "/ask",
                                        {"question": "Why the Responses API as a new class?"}, "tok-a")
            self.assertEqual(status, 200)

            # tok-a is now exhausted...
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post_with_auth(fx.base + "/ask",
                                {"question": "Why the Responses API as a new class?"}, "tok-a")
            self.assertEqual(cm.exception.code, 429)
            cm.exception.close()

            # ...but tok-b (a different identity) still has its own budget.
            status, _ = _post_with_auth(fx.base + "/ask",
                                        {"question": "Why the Responses API as a new class?"}, "tok-b")
            self.assertEqual(status, 200)
        finally:
            fx.close()


def _post_with_auth(url, obj, token):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class LazyRegistryTests(unittest.TestCase):
    """_LazyRegistry: the fix for a real deploy failure (docs/HANDOFF.md's D5
    section) where LibraryRegistry's cold corpus-embed blocked serve() from
    ever binding its port, timing out Render's post-bind port-scan gate."""

    def test_raises_warming_until_build_completes(self):
        from .server import _LazyRegistry, _RegistryWarming
        release = threading.Event()
        built = _StubRegistry(_StubLibrary())

        def slow_build():
            release.wait(timeout=5)
            return built

        reg = _LazyRegistry(slow_build)
        with self.assertRaises(_RegistryWarming):
            reg.library_for("alice")
        with self.assertRaises(_RegistryWarming):
            reg.disconnect("alice")

        release.set()
        # Poll briefly for the background thread to finish -- no fixed sleep.
        import time
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                reg.library_for("alice")
                break
            except _RegistryWarming:
                time.sleep(0.01)
        self.assertEqual(reg.library_for("alice"), built.lib)
        reg.disconnect("alice")
        self.assertEqual(built.disconnected, ["alice"])

    def test_build_failure_is_raised_not_swallowed(self):
        from .server import _LazyRegistry
        import time

        def failing_build():
            raise RuntimeError("boom")

        reg = _LazyRegistry(failing_build)
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                reg.library_for("alice")
            except RuntimeError as e:
                self.assertEqual(str(e), "boom")
                return
            except Exception:
                time.sleep(0.01)
        self.fail("build failure was never raised")


class RegistryWarmupHttpTests(unittest.TestCase):
    """The HTTP-level wiring: while the registry is still warming, the port
    is already accepting connections (proven by every request below actually
    completing), /health answers 200 (a PaaS liveness check shouldn't flap
    mid-warmup), and every registry-dependent route answers an honest 503
    instead of hanging. Once warmup completes, normal routing resumes."""

    def test_health_ok_during_warmup_then_status_503_then_ready(self):
        from .server import _LazyRegistry
        import time

        release = threading.Event()
        built = _StubRegistry(_StubLibrary())

        def slow_build():
            release.wait(timeout=5)
            return built

        lazy = _LazyRegistry(slow_build)
        fx = _ServerFixture(lazy)
        try:
            # /health is up immediately and answers honestly that it's still starting.
            with urllib.request.urlopen(fx.base + "/health", timeout=3) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(json.loads(resp.read())["state"], "starting")

            # /status needs a real registry -- honest 503, not a hang or a crash.
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(fx.base + "/status", timeout=3)
            self.assertEqual(cm.exception.code, 503)
            cm.exception.close()

            release.set()
            deadline = time.time() + 5
            while time.time() < deadline:
                with urllib.request.urlopen(fx.base + "/status", timeout=3) as resp:
                    if resp.status == 200:
                        break
                time.sleep(0.01)
            with urllib.request.urlopen(fx.base + "/health", timeout=3) as resp:
                body = json.loads(resp.read())
                self.assertEqual(body["repo"], REPO)
        finally:
            fx.close()


class SyncConnectTests(unittest.TestCase):
    """sync_connect=True (ICARUS_SYNC_CONNECT): /connect blocks on the real
    connect_sync() and returns its final status, instead of backgrounding it
    and returning 202 immediately. Needed on request-scoped-CPU platforms
    (Cloud Run, Azure Container Apps) where a background thread's embed work
    after the response returns isn't reliably resourced."""

    def test_sync_connect_returns_final_status_not_202(self):
        lib = _StubLibrary()
        fx = _ServerFixture(lib, sync_connect=True)
        try:
            status, payload = _post(fx.base + "/connect", {"repo": "octocat/hello"})
            self.assertEqual(status, 200)  # not 202 -- this IS the final status
            self.assertEqual(payload["state"], "ready")
            self.assertEqual(payload["repo"], REPO)
            # No polling needed: by the time the response arrived, connect_sync
            # already ran to completion on the request's own thread.
            self.assertIn("octocat/hello", lib.connected)
        finally:
            fx.close()

    def test_sync_connect_actually_blocks_on_a_slow_connect(self):
        # Proves the request genuinely WAITS for connect_sync, not that it just
        # happens to be fast in this test -- same Event-gated idiom as
        # ConcurrencyTests' _SlowLibrary above.
        import time
        release = threading.Event()

        class _SlowLibrary(_StubLibrary):
            def connect_sync(self, repo, token=None, private=False, background_upgrade=False):
                release.wait(timeout=5)
                return super().connect_sync(repo, token=token, private=private,
                                            background_upgrade=background_upgrade)

        lib = _SlowLibrary()
        fx = _ServerFixture(lib, sync_connect=True)
        try:
            result = {}

            def do_connect():
                result["status"], result["payload"] = _post(
                    fx.base + "/connect", {"repo": "octocat/hello"})

            t = threading.Thread(target=do_connect, daemon=True)
            t.start()
            time.sleep(0.2)
            # Still blocked -- connect_sync hasn't been released yet.
            self.assertNotIn("octocat/hello", lib.connected)
            release.set()
            t.join(timeout=5)
            self.assertEqual(result["status"], 200)
            self.assertIn("octocat/hello", lib.connected)
        finally:
            fx.close()

    def test_background_mode_unaffected_by_default(self):
        # sync_connect's default (False) must reproduce today's behavior
        # exactly: 202 immediately, connect_sync finishes on its own thread.
        import time
        lib = _StubLibrary()
        fx = _ServerFixture(lib)  # no sync_connect kwarg -- default
        try:
            status, payload = _post(fx.base + "/connect", {"repo": "octocat/hello"})
            self.assertEqual(status, 202)
            self.assertEqual(payload["state"], "indexing")
            for _ in range(50):
                if "octocat/hello" in lib.connected:
                    break
                time.sleep(0.02)
            self.assertIn("octocat/hello", lib.connected)
        finally:
            fx.close()

    def test_background_upgrade_flag_is_forwarded_to_connect_sync(self):
        # Option B (ICARUS_BACKGROUND_UPGRADE): a sync /connect must forward
        # background_upgrade=True so connect_sync backgrounds STAGE 2's embed.
        lib = _StubLibrary()
        fx = _ServerFixture(lib, sync_connect=True, background_upgrade=True)
        try:
            status, _ = _post(fx.base + "/connect", {"repo": "octocat/hello"})
            self.assertEqual(status, 200)
            self.assertEqual(lib.background_upgrades, [True])
        finally:
            fx.close()

    def test_sync_connect_defaults_to_blocking_embed(self):
        # Without the flag the sync path keeps blocking through the embed
        # (background_upgrade=False) -- the safe default for scale-to-zero.
        lib = _StubLibrary()
        fx = _ServerFixture(lib, sync_connect=True)
        try:
            _post(fx.base + "/connect", {"repo": "octocat/hello"})
            self.assertEqual(lib.background_upgrades, [False])
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()


# --- T3: entitlement enforced on reads -------------------------------------
# Once a repo's index is SHARED, the storage layout stops being the isolation
# and this check becomes it. These tests pin the failure direction: ambiguity
# denies, and a denied caller must never reach the billed writer.

class _CountingPipeline(Pipeline):
    """Records whether the (billed) writer was reached at all."""

    def __init__(self):
        self.answer_calls = 0
        self.explain_calls = 0

    def answer(self, question, token=None):
        self.answer_calls += 1
        return Result(verdict="unknown", retrieved=[])

    def explain(self, path, start, end, question=None):
        self.explain_calls += 1
        return Result(verdict="unknown", retrieved=[])


class _RepoLibrary(_StubLibrary):
    """A library whose active repo is configurable (the default demo repo is
    special-cased by the guard, so tests need a NON-default repo)."""

    def __init__(self, repo, pipeline=None):
        super().__init__()
        self._repo = repo
        if pipeline is not None:
            self._pipe = pipeline

    def provenance(self):
        return (self._repo, COMMIT)

    def status_snapshot(self):
        snap = super().status_snapshot()
        snap["repo"] = self._repo
        return snap


class _StubAccess:
    """Stand-in for RepoAccessVerifier: allows the listed (repo, token) pairs."""

    def __init__(self, allowed=()):
        self._allowed = set(allowed)
        self.calls = []

    def can_read(self, repo, token):
        self.calls.append((repo, token))
        return (repo, token) in self._allowed


def _ask_as(base, token, question="anything"):
    data = json.dumps({"question": question}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + "/ask", data=data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class ReadEntitlementTests(unittest.TestCase):
    PRIVATE = "acme/secrets"

    def _fixture(self, allowed=(), pipeline=None):
        from .auth import StaticTokenVerifier
        lib = _RepoLibrary(self.PRIVATE, pipeline=pipeline)
        return _ServerFixture(
            lib, require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"}),
            access_verifier=_StubAccess(allowed),
            default_repo=REPO,
        ), lib

    def test_caller_without_repo_access_is_refused(self):
        fx, _ = self._fixture(allowed=[(self.PRIVATE, "tok-a")])
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _ask_as(fx.base, "tok-b")          # valid identity, no repo access
            self.assertEqual(cm.exception.code, 403)
        finally:
            fx.close()

    def test_refused_caller_never_reaches_the_billed_writer(self):
        # The whole point of checking before the pipeline: a refused request must
        # cost nothing at the model provider.
        pipe = _CountingPipeline()
        fx, _ = self._fixture(allowed=[(self.PRIVATE, "tok-a")], pipeline=pipe)
        try:
            with self.assertRaises(urllib.error.HTTPError):
                _ask_as(fx.base, "tok-b")
            self.assertEqual(pipe.answer_calls, 0, "a denied caller must not bill the writer")
        finally:
            fx.close()

    def test_entitled_caller_gets_an_answer(self):
        fx, _ = self._fixture(allowed=[(self.PRIVATE, "tok-a")])
        try:
            status, body = _ask_as(fx.base, "tok-a")
            self.assertEqual(status, 200)
            self.assertIn("verdict", body)
        finally:
            fx.close()

    def test_explain_is_guarded_the_same_way(self):
        # /explain reads the same corpus; guarding /ask alone would leave the
        # side door open.
        fx, _ = self._fixture(allowed=[(self.PRIVATE, "tok-a")])
        try:
            data = json.dumps({"repo": self.PRIVATE, "path": "a.py",
                               "start": 1, "end": 5}).encode()
            req = urllib.request.Request(
                fx.base + "/explain", data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer tok-b"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 403)
        finally:
            fx.close()

    def test_builtin_demo_repo_needs_no_entitlement_check(self):
        # The public demo must keep working for anyone signed in, and must not
        # burn a GitHub API call to prove what is already public.
        from .auth import StaticTokenVerifier
        access = _StubAccess()                      # allows nothing
        fx = _ServerFixture(_RepoLibrary(REPO), require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}),
                            access_verifier=access, default_repo=REPO)
        try:
            status, _ = _ask_as(fx.base, "tok-a")
            self.assertEqual(status, 200)
            self.assertEqual(access.calls, [], "the built-in repo needs no check")
        finally:
            fx.close()

    def test_local_mode_is_unaffected(self):
        # Auth off = a single local operator on loopback. There is no tenancy to
        # enforce, and demanding a GitHub token would break local development.
        access = _StubAccess()
        fx = _ServerFixture(_RepoLibrary(self.PRIVATE), access_verifier=access,
                            default_repo=REPO)
        try:
            status, _ = _ask_as(fx.base, None)
            self.assertEqual(status, 200)
            self.assertEqual(access.calls, [])
        finally:
            fx.close()


# --- T4: the shared ask ledger ---------------------------------------------

class AskLedgerTests(unittest.TestCase):
    """Every ask is recorded against the REPO, so a team accumulates one record
    instead of N private histories -- and the unknowns become a map of what the
    organisation never wrote down."""

    PRIVATE = "acme/secrets"

    def setUp(self):
        from .auth import StaticTokenVerifier
        from .ledger import Ledger
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.tmp.name) / "ledger")
        self.fx = _ServerFixture(
            _RepoLibrary(self.PRIVATE), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"}),
            access_verifier=_StubAccess([(self.PRIVATE, "tok-a")]),
            default_repo=REPO, ledger=self.ledger)
        self.base = self.fx.base

    def tearDown(self):
        self.fx.close()
        self.tmp.cleanup()

    def _get(self, path, token):
        req = urllib.request.Request(self.base + path,
                                     headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def test_an_ask_is_recorded_against_the_repo(self):
        _ask_as(self.base, "tok-a", "Why the Responses API as a new class?")
        got = self.ledger.entries(self.PRIVATE)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["question"], "Why the Responses API as a new class?")
        self.assertEqual(got[0]["verdict"], "answer")

    def test_an_honest_unknown_is_recorded_as_a_gap(self):
        # The whole point: the questions nobody could answer are the asset.
        _ask_as(self.base, "tok-a", "something nobody documented")
        gaps = self.ledger.entries(self.PRIVATE, unknowns_only=True)
        self.assertEqual([e["question"] for e in gaps], ["something nobody documented"])

    def test_ledger_endpoint_returns_the_teams_questions(self):
        _ask_as(self.base, "tok-a", "Why the Responses API as a new class?")
        status, body = self._get("/ledger", "tok-a")
        self.assertEqual(status, 200)
        self.assertEqual(body["repo"], self.PRIVATE)
        self.assertEqual(len(body["entries"]), 1)

    def test_ledger_endpoint_can_filter_to_unknowns(self):
        _ask_as(self.base, "tok-a", "Why the Responses API as a new class?")   # answered
        _ask_as(self.base, "tok-a", "undocumented thing")                       # unknown
        _, body = self._get("/ledger?unknowns=1", "tok-a")
        self.assertEqual([e["question"] for e in body["entries"]], ["undocumented thing"])

    def test_the_ledger_is_guarded_by_the_same_entitlement_check(self):
        # It contains the team's questions about their own private code, so it
        # is at least as sensitive as the corpus and must not be more readable.
        _ask_as(self.base, "tok-a", "Why the Responses API as a new class?")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/ledger", "tok-b")
        self.assertEqual(cm.exception.code, 403)

    def test_a_broken_ledger_never_breaks_answering(self):
        # The ledger is an asset, not a dependency: if recording fails, the user
        # must still get the answer they asked for.
        class _Boom:
            def record(self, *a, **k):
                raise RuntimeError("disk on fire")

            def entries(self, *a, **k):
                return []
        from .auth import StaticTokenVerifier
        fx = _ServerFixture(
            _RepoLibrary(self.PRIVATE), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "1001"}),
            access_verifier=_StubAccess([(self.PRIVATE, "tok-a")]),
            default_repo=REPO, ledger=_Boom())
        try:
            status, body = _ask_as(fx.base, "tok-a", "Why the Responses API as a new class?")
            self.assertEqual(status, 200)
            self.assertIn("verdict", body)
        finally:
            fx.close()


# --- The repository map -----------------------------------------------------

class _MappedPipeline(_StubPipeline):
    """A pipeline holding a small corpus that REFUSES to answer -- so a /map
    test that accidentally reaches the writer fails loudly instead of passing."""

    CHUNKS = [
        ("code:llm/cli.py#L1-L300", "import click\n"),
        ("code:llm/cli.py#L261-L560", 'if __name__ == "__main__":\n    cli()\n'),
        ("doc:README.md", "# llm\n"),
        ("config:pyproject.toml", '[project.scripts]\nllm = "llm.cli:cli"\n'),
        ("pr:1435", "a pull request"),
        ("issue:900", "an issue"),
    ]

    def indexed_chunks(self):
        from evals.corpus import Chunk
        return [Chunk(ref=r, source=r.split(":", 1)[0], text=t) for r, t in self.CHUNKS]

    def answer(self, question, token=None):
        raise AssertionError("/map must not call the writer")


class RepoMapEndpointTests(unittest.TestCase):
    """GET /map: what Icarus has indexed, before anyone asks a question.

    Guarded exactly like /ledger -- a private repo's file paths are at least as
    sensitive as the corpus itself, so the map is entitlement-checked, never
    served on a weaker gate than the answers it describes.
    """

    PRIVATE = "acme/secrets"

    def setUp(self):
        from .auth import StaticTokenVerifier
        self.fx = _ServerFixture(
            _RepoLibrary(self.PRIVATE, pipeline=_MappedPipeline()), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"}),
            access_verifier=_StubAccess([(self.PRIVATE, "tok-a")]),
            default_repo=REPO)
        self.base = self.fx.base

    def tearDown(self):
        self.fx.close()

    def _get(self, path, token):
        req = urllib.request.Request(self.base + path,
                                     headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def test_map_reports_the_indexed_corpus(self):
        status, body = self._get("/map", "tok-a")
        self.assertEqual(status, 200)
        self.assertEqual(body["repo"], self.PRIVATE)
        self.assertEqual(body["indexed_file_count"], 3)  # cli.py counted ONCE
        self.assertEqual(body["indexed_documentation"]["readme"], "README.md")

    def test_map_needs_no_model_call(self):
        # _MappedPipeline.answer raises; reaching it would 503 or 500 here.
        status, _ = self._get("/map", "tok-a")
        self.assertEqual(status, 200)

    def test_map_is_entitlement_checked(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self._get("/map", "tok-b")
        self.assertEqual(e.exception.code, 403)

    def test_map_requires_a_signed_in_caller(self):
        req = urllib.request.Request(self.base + "/map")
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 401)

    def test_map_reports_entry_points_with_their_rules(self):
        _, body = self._get("/map", "tok-a")
        entries = body["indexed_entry_points"]
        self.assertEqual([e["path"] for e in entries], ["llm/cli.py"])
        rules = {r["rule"] for r in entries[0]["rules"]}
        self.assertEqual(rules, {"conventional-filename", "pyproject-console-script",
                                 "python-main-guard"})
        for rule in entries[0]["rules"]:
            self.assertIn(rule["evidence_ref"],
                          [ref for ref, _ in _MappedPipeline.CHUNKS])

    def test_map_never_claims_repository_completeness(self):
        _, body = self._get("/map", "tok-a")
        self.assertTrue(body["limitations"])
        for forbidden in ("total_files", "excluded_files", "excluded_file_count"):
            self.assertNotIn(forbidden, body)


# --- The guided onboarding tour ---------------------------------------------

class _TourPipeline(_StubPipeline):
    """A pipeline with a README, recording which path each step took."""

    CHUNKS = [("doc:README.md", "# llm\nA CLI for large language models.\n"),
              ("code:llm/cli.py", "import click\n"), ("pr:1435", "a pull request")]

    def __init__(self):
        self.answered, self.explained = [], []

    def indexed_chunks(self):
        from evals.corpus import Chunk
        return [Chunk(ref=r, source=r.split(":", 1)[0], text=t) for r, t in self.CHUNKS]

    def answer(self, question, token=None):
        self.answered.append(question)
        return Result(verdict="answer", answer="Because of X.", citations=["pr:1435"],
                      retrieved=["pr:1435"])

    def explain(self, path, start, end, question=None):
        self.explained.append((path, question))
        return Result(verdict="answer", answer="A CLI for large language models.",
                      citations=["doc:README.md"], retrieved=["doc:README.md"])


class OnboardingEndpointTests(unittest.TestCase):
    """GET /onboarding -> the plan; POST /onboarding {step} -> one cited step.

    Stateless on purpose: the plan is a constant and each step is fetched on
    its own, so "interrupt with a question and come back" needs no session and
    nothing can be lost by resuming.
    """

    PRIVATE = "acme/secrets"

    def setUp(self):
        from .auth import StaticTokenVerifier
        from .ledger import Ledger
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.tmp.name) / "ledger")
        self.pipe = _TourPipeline()
        self.fx = _ServerFixture(
            _RepoLibrary(self.PRIVATE, pipeline=self.pipe), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"}),
            access_verifier=_StubAccess([(self.PRIVATE, "tok-a")]),
            default_repo=REPO, ledger=self.ledger)
        self.base = self.fx.base

    def tearDown(self):
        self.fx.close()
        self.tmp.cleanup()

    def _get(self, path, token):
        req = urllib.request.Request(self.base + path,
                                     headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def _post(self, obj, token):
        req = urllib.request.Request(
            self.base + "/onboarding", data=json.dumps(obj).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def test_the_plan_lists_the_tour(self):
        status, body = self._get("/onboarding", "tok-a")
        self.assertEqual(status, 200)
        self.assertEqual(body["repo"], self.PRIVATE)
        self.assertEqual([s["id"] for s in body["steps"]],
                         ["overview", "purpose", "stack", "decisions", "conventions", "recent"])

    def test_the_plan_costs_no_writer_call(self):
        self._get("/onboarding", "tok-a")
        self.assertEqual(self.pipe.answered, [])
        self.assertEqual(self.pipe.explained, [])

    def test_a_step_returns_the_same_shape_as_ask(self):
        # Same payload as /ask, so every client renders the tour with the
        # renderer it already has -- citations, excerpts and all.
        status, body = self._post({"step": "stack"}, "tok-a")
        self.assertEqual(status, 200)
        self.assertEqual(body["verdict"], "answer")
        self.assertTrue(body["citations"])
        self.assertEqual(body["step"], "stack")
        self.assertTrue(body["title"])

    def test_purpose_addresses_the_readme(self):
        _, body = self._post({"step": "purpose"}, "tok-a")
        self.assertEqual([p for p, _q in self.pipe.explained], ["README.md"])
        self.assertEqual(body["citations"][0]["ref"], "doc:README.md")

    def test_an_unknown_step_is_a_clean_400(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self._post({"step": "architecture"}, "tok-a")   # measured out of the tour
        self.assertEqual(e.exception.code, 400)

    def test_a_missing_step_is_a_clean_400(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self._post({}, "tok-a")
        self.assertEqual(e.exception.code, 400)

    def test_the_tour_is_entitlement_checked(self):
        for call in (lambda: self._get("/onboarding", "tok-b"),
                     lambda: self._post({"step": "stack"}, "tok-b")):
            with self.assertRaises(urllib.error.HTTPError) as e:
                call()
            self.assertEqual(e.exception.code, 403)

    def test_the_tour_requires_a_signed_in_caller(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(self.base + "/onboarding")
        self.assertEqual(e.exception.code, 401)

    def test_the_tour_never_writes_to_the_ask_ledger(self):
        # The ledger ranks gaps by how OFTEN a question was asked. Machine-
        # generated tour steps, asked once per connect per user, would swamp
        # the real questions a team asked and invent documentation debt that
        # nobody was actually looking for.
        self._post({"step": "stack"}, "tok-a")
        self._post({"step": "purpose"}, "tok-a")
        self.assertEqual(self.ledger.entries(self.PRIVATE), [])
