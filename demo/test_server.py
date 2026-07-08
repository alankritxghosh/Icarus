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

    def answer(self, question):
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
        self.connect_calls = []  # (repo, token, private) for tests that need kwargs

    def current_pipeline(self):
        return self._pipe

    def provenance(self):
        return (REPO, COMMIT)

    def status_snapshot(self):
        return {"state": "ready", "repo": REPO, "commit": COMMIT, "counts": None, "error": None,
                "private": False}

    def connect_sync(self, repo, token=None, private=False):
        self.connected.append(repo)
        self.connect_calls.append((repo, token, private))


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
            handler = make_handler(_SlowLibrary(), str(html))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = server.server_port
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            try:
                slow = threading.Thread(
                    target=lambda: urllib.request.urlopen(base + "/status", timeout=5).read(),
                    daemon=True)
                slow.start()
                time.sleep(0.2)
                start = time.time()
                with urllib.request.urlopen(base + "/", timeout=3) as resp:
                    self.assertEqual(resp.status, 200)
                self.assertLess(time.time() - start, 2.0)
            finally:
                release.set()
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

    def _begin_mode(self, mode):
        req = urllib.request.Request(
            self.base + "/auth/github/begin",
            data=json.dumps({"mode": mode}).encode(),
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


class PrivateConnectRouteTests(unittest.TestCase):
    """/connect must verify caller access BEFORE spawning any background work
    when auth is required, and route private/public repos correctly. In local
    dev (auth off) the behavior is untouched: no access check at all."""

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

    def test_private_repo_spawns_connect_with_token_and_private_true(self):
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
        self.assertEqual(lib.connect_calls, [("acme/secret", "tok-a", True)])

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
        self.assertEqual(lib.connect_calls, [("octo/pub", None, False)])

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
        self.assertEqual(lib.connect_calls, [("octo/pub", None, False)])


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


if __name__ == "__main__":
    unittest.main()
