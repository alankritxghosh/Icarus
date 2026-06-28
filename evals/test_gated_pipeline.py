# evals/test_gated_pipeline.py
import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline

CHUNKS = [
    Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
    Chunk("pr:2", "pr", "bump version"),
]


def _pipe(provider):
    return GatedPipeline(LexicalRetriever(CHUNKS), CHUNKS, provider)


class GatedPipelineTests(unittest.TestCase):
    def test_emits_grounded_answer(self):
        raw = json.dumps({"verdict": "answer", "answer": "Because fetch stubbing broke.", "citations": ["pr:1"]})
        r = _pipe(StaticProvider(raw)).answer("why MSW instead of stubbing fetch")
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:1", r.citations)

    def test_abstains_when_writer_abstains(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW")
        self.assertEqual(r.verdict, "unknown")

    def test_bluff_with_unretrieved_citation_is_forced_unknown(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        self.assertEqual(_pipe(StaticProvider(raw)).answer("why MSW").verdict, "unknown")

    def test_populates_retrieved_for_recall(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW instead of stubbing fetch")
        self.assertIn("pr:1", r.retrieved)  # recall@k still measurable even on abstain


if __name__ == "__main__":
    unittest.main()
