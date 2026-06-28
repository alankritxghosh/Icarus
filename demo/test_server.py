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
        handler = make_handler(_StubPipeline(), REPO, COMMIT, str(cls.html))
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


if __name__ == "__main__":
    unittest.main()
