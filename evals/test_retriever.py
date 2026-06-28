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


if __name__ == "__main__":
    unittest.main()
