# evals/test_retriever.py
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever, tokenize


class TokenizeTests(unittest.TestCase):
    def test_lowercases_and_splits_on_non_word(self):
        self.assertEqual(tokenize("Why MSW, not fetch?"), ["why", "msw", "not", "fetch"])


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
            Chunk("pr:2", "pr", "Bump version and update changelog"),
            Chunk("code:a.py", "code", "def add(a, b): return a + b"),
        ]
        self.r = LexicalRetriever(self.chunks)

    def test_ranks_relevant_chunk_first(self):
        self.assertEqual(self.r.search("why do we mock with MSW instead of stubbing fetch", k=3)[0], "pr:1")

    def test_returns_at_most_k_refs(self):
        self.assertLessEqual(len(self.r.search("mock", k=1)), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(self.r.search("xyzzy nonexistentterm", k=3), [])

    def test_ties_break_by_ref_ascending(self):
        # identical text -> identical score -> deterministic ref-ascending order.
        # This determinism is load-bearing for reproducible eval scores.
        chunks = [Chunk("pr:9", "pr", "alpha"), Chunk("pr:1", "pr", "alpha"), Chunk("pr:5", "pr", "alpha")]
        self.assertEqual(LexicalRetriever(chunks).search("alpha", k=3), ["pr:1", "pr:5", "pr:9"])

    def test_empty_corpus_returns_empty(self):
        self.assertEqual(LexicalRetriever([]).search("anything", k=3), [])

    def test_zero_score_chunk_dropped_from_mixed_result(self):
        chunks = [Chunk("pr:1", "pr", "msw mocking rationale"), Chunk("pr:2", "pr", "completely unrelated")]
        self.assertEqual(LexicalRetriever(chunks).search("msw", k=5), ["pr:1"])

    def test_truncates_to_k(self):
        chunks = [Chunk(f"pr:{i}", "pr", "common term") for i in range(5)]
        self.assertEqual(len(LexicalRetriever(chunks).search("common", k=2)), 2)


if __name__ == "__main__":
    unittest.main()
