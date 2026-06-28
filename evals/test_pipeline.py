# evals/test_pipeline.py
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .pipeline import RetrievalPipeline


class RetrievalPipelineTests(unittest.TestCase):
    def setUp(self):
        chunks = [Chunk("pr:1", "pr", "mock with MSW because stubbing fetch broke")]
        self.p = RetrievalPipeline(LexicalRetriever(chunks))

    def test_populates_retrieved(self):
        self.assertIn("pr:1", self.p.answer("why MSW instead of stubbing fetch").retrieved)

    def test_still_abstains(self):
        r = self.p.answer("why MSW instead of stubbing fetch")
        self.assertEqual(r.verdict, "unknown")   # gates stay trivially intact
        self.assertEqual(r.citations, [])         # makes no claims yet


if __name__ == "__main__":
    unittest.main()
