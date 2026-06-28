# demo/test_payload.py
import unittest

from evals.pipeline import Result
from .payload import build_payload

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"


class BuildPayloadTests(unittest.TestCase):
    def test_answer_carries_prose_and_citation_urls(self):
        r = Result(verdict="answer", answer="Because Y.",
                   citations=["pr:1435"], retrieved=["pr:1435", "code:llm/x.py"])
        p = build_payload(r, REPO, COMMIT)
        self.assertEqual(p["verdict"], "answer")
        self.assertEqual(p["answer"], "Because Y.")
        self.assertEqual(p["citations"], [{"ref": "pr:1435", "url": "https://github.com/simonw/llm/pull/1435"}])
        self.assertEqual(p["searched"], ["pr:1435", "code:llm/x.py"])

    def test_unknown_is_empty_answer_no_citations_but_shows_searched(self):
        r = Result(verdict="unknown", retrieved=["code:llm/x.py", "code:llm/y.py"])
        p = build_payload(r, REPO, COMMIT)
        self.assertEqual(p["verdict"], "unknown")
        self.assertEqual(p["answer"], "")
        self.assertEqual(p["citations"], [])
        self.assertEqual(p["searched"], ["code:llm/x.py", "code:llm/y.py"])

    def test_citations_preserve_order(self):
        r = Result(verdict="answer", answer="a", citations=["pr:2", "pr:1"],
                   retrieved=["pr:2", "pr:1"])
        self.assertEqual([c["ref"] for c in build_payload(r, REPO, COMMIT)["citations"]], ["pr:2", "pr:1"])

    def test_citation_without_url_still_appears(self):
        r = Result(verdict="answer", answer="a", citations=["slack:9"], retrieved=["slack:9"])
        self.assertEqual(build_payload(r, REPO, COMMIT)["citations"], [{"ref": "slack:9", "url": None}])


if __name__ == "__main__":
    unittest.main()
