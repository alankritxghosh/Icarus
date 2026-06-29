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

from . import server
from .library import Library

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "evals" / "corpus" / "chunks.jsonl"
QUESTIONS = json.loads((ROOT.parent / "evals" / "phase1_questions.json").read_text())
_HAS_KEY = any(os.environ.get(k) for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"))


def _post(base, question):
    data = json.dumps({"question": question}).encode()
    req = urllib.request.Request(base + "/ask", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


@unittest.skipUnless(_HAS_KEY and CORPUS.exists(),
                     "needs a provider key (GROQ/GEMINI/OPENROUTER) and the corpus")
class DemoLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        default_repo, _ = server.resolve_provenance(server.CORPUS_META, server.QUESTIONS)
        lib = Library(server.CORPUS_DIR, server.CACHE_ROOT, default_repo)
        handler = server.make_handler(lib, str(server.INDEX_HTML))
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_some_answerable_returns_cited_answer(self):
        # The free writer is non-deterministic and abstains on some answerable
        # questions (an honest false-abstention, not a bluff). The face is wired
        # correctly as long as AT LEAST ONE answerable yields a grounded, cited
        # answer; assert that and short-circuit to spare the daily free quota.
        answerable = [x["question"] for x in QUESTIONS["questions"] if x["label"] == "answerable"]
        for q in answerable:
            p = _post(self.base, q)
            if p["verdict"] == "answer" and any("github.com" in (c["url"] or "") for c in p["citations"]):
                return  # found a cited answer -> the wiring works
        self.fail("no answerable question produced a cited answer with a github link")

    def test_unrecorded_returns_honest_unknown(self):
        q = next(x["question"] for x in QUESTIONS["questions"] if x["label"] == "unanswerable")
        p = _post(self.base, q)
        self.assertEqual(p["verdict"], "unknown")
        self.assertEqual(p["answer"], "")


if __name__ == "__main__":
    unittest.main()
