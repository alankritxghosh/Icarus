# demo/test_server.py
import json
import tempfile
import threading
import unittest
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


class _StubLibrary:
    """Stand-in for demo.library.Library: fixed pipeline, records connects."""

    def __init__(self):
        self._pipe = _StubPipeline()
        self.connected = []

    def current_pipeline(self):
        return self._pipe

    def provenance(self):
        return (REPO, COMMIT)

    def status_snapshot(self):
        return {"state": "ready", "repo": REPO, "commit": COMMIT, "counts": None, "error": None}

    def connect_sync(self, repo):
        self.connected.append(repo)


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
        handler = make_handler(cls.lib, str(cls.html))
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

    def test_posts_to_ask_and_handles_both_verdicts(self):
        self.assertIn("/ask", self.html)
        self.assertIn('verdict', self.html)

    def test_renders_the_honest_unknown_hero(self):
        self.assertIn("No one wrote this down", self.html)

    def test_has_repo_connect_controls(self):
        self.assertIn('id="repo"', self.html)
        self.assertIn("/connect", self.html)
        self.assertIn("/status", self.html)


if __name__ == "__main__":
    unittest.main()
