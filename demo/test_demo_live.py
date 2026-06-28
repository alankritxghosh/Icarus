# demo/test_demo_live.py
"""End-to-end guard against the REAL pipeline: an answerable question returns a
cited answer with a github.com link; an unrecorded code question returns the
honest unknown. Thin -- the brain's correctness is proven by the eval board;
this only proves the face is wired to it. Skips without key/corpus."""

import json
import os
import threading
import unittest
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from evals.corpus import load_chunks
from evals.retriever import LexicalRetriever
from evals.provider import OpenRouterProvider
from evals.pipeline import GatedPipeline
from .server import make_handler, INDEX_HTML

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "evals" / "corpus" / "chunks.jsonl"
QUESTIONS = json.loads((ROOT.parent / "evals" / "phase1_questions.json").read_text())


def _post(base, question):
    data = json.dumps({"question": question}).encode()
    req = urllib.request.Request(base + "/ask", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


@unittest.skipUnless(os.environ.get("OPENROUTER_API_KEY") and CORPUS.exists(),
                     "needs OPENROUTER_API_KEY and the corpus")
class DemoLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        corpus = QUESTIONS["corpus"]
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, OpenRouterProvider())
        handler = make_handler(pipe, corpus["repo"], corpus["commit"], str(INDEX_HTML))
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_answerable_returns_cited_answer(self):
        q = next(x["question"] for x in QUESTIONS["questions"] if x["label"] == "answerable")
        p = _post(self.base, q)
        self.assertEqual(p["verdict"], "answer")
        self.assertTrue(p["citations"])
        self.assertTrue(any("github.com" in (c["url"] or "") for c in p["citations"]))

    def test_unrecorded_returns_honest_unknown(self):
        q = next(x["question"] for x in QUESTIONS["questions"] if x["label"] == "unanswerable")
        p = _post(self.base, q)
        self.assertEqual(p["verdict"], "unknown")
        self.assertEqual(p["answer"], "")


if __name__ == "__main__":
    unittest.main()
