# evals/test_retriever.py
import unittest

from .corpus import Chunk
from .provider import StaticEmbeddingProvider
from .retriever import LexicalRetriever, SemanticRetriever, _cosine, tokenize


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


class CosineTests(unittest.TestCase):
    def test_identical_vectors_have_similarity_one(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_opposite_vectors_have_similarity_negative_one(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_orthogonal_vectors_have_similarity_zero(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_hand_verified_pair(self):
        # dot = 1*0.9 + 0*0.1 = 0.9; |a|=1.0; |b|=sqrt(0.81+0.01)=sqrt(0.82)
        # cos = 0.9 / sqrt(0.82) ~= 0.99388373...
        self.assertAlmostEqual(_cosine([1.0, 0.0], [0.9, 0.1]), 0.9938837346736189)

    def test_zero_vector_does_not_crash_and_returns_zero(self):
        self.assertEqual(_cosine([0.0, 0.0], [1.0, 0.0]), 0.0)
        self.assertEqual(_cosine([1.0, 0.0], [0.0, 0.0]), 0.0)
        self.assertEqual(_cosine([0.0, 0.0], [0.0, 0.0]), 0.0)


class SemanticRetrieverTests(unittest.TestCase):
    def setUp(self):
        # Target chunk describes an auth/login flow but never uses the word
        # "login" (or any token the paraphrased query uses) -- verified via
        # tokenize() in test_paraphrase_shares_no_bm25_tokens_with_target below.
        self.target_text = "validates a users credentials and issues a session cookie"
        self.unrelated1_text = "the recipe calls for two cups of flour and a pinch of salt"
        self.unrelated2_text = "the weather forecast predicts rain over the weekend"
        self.query = "how does login work"

        self.chunks = [
            Chunk("code:auth.py", "code", self.target_text),
            Chunk("code:recipe.py", "code", self.unrelated1_text),
            Chunk("code:weather.py", "code", self.unrelated2_text),
        ]

        # Hand-picked 2D vectors: the query sits close to the target (small
        # angle, cosine ~0.994), opposite the first unrelated chunk (cosine
        # -1.0), and orthogonal to the second (cosine 0.0).
        vectors = {
            self.query: [1.0, 0.0],
            self.target_text: [0.9, 0.1],
            self.unrelated1_text: [-1.0, 0.0],
            self.unrelated2_text: [0.0, 1.0],
        }
        self.provider = StaticEmbeddingProvider(vectors)
        self.retriever = SemanticRetriever(self.chunks, self.provider)

    def test_paraphrase_shares_no_bm25_tokens_with_target(self):
        # The exact claim Brick C exists to prove depends on this being true --
        # verify it directly rather than assuming it.
        self.assertEqual(set(tokenize(self.query)) & set(tokenize(self.target_text)), set())

    def test_semantic_retriever_ranks_paraphrased_target_first(self):
        self.assertEqual(self.retriever.search(self.query, k=3)[0], "code:auth.py")

    def test_lexical_retriever_fails_on_the_same_paraphrased_query(self):
        # Same chunks, same query: BM25 has zero keyword overlap with the
        # target chunk, so it returns nothing -- this is the gap Brick C closes.
        self.assertEqual(LexicalRetriever(self.chunks).search(self.query, k=3), [])

    def test_returns_at_most_k_refs(self):
        self.assertLessEqual(len(self.retriever.search(self.query, k=1)), 1)

    def test_orthogonal_chunk_dropped_as_non_positive_similarity(self):
        # unrelated2 is exactly orthogonal (cosine 0.0) to the query -- dropped
        # by the same "> 0" convention LexicalRetriever uses for a zero score.
        results = self.retriever.search(self.query, k=3)
        self.assertNotIn("code:weather.py", results)

    def test_negative_similarity_chunk_dropped(self):
        results = self.retriever.search(self.query, k=3)
        self.assertNotIn("code:recipe.py", results)

    def test_ties_break_by_ref_ascending(self):
        # Identical vectors -> identical similarity -> deterministic ref-ascending
        # order, mirroring LexicalRetriever's tie-break convention exactly.
        chunks = [Chunk("pr:9", "pr", "alpha"), Chunk("pr:1", "pr", "alpha"), Chunk("pr:5", "pr", "alpha")]
        provider = StaticEmbeddingProvider({"alpha": [1.0, 0.0], "query": [1.0, 0.0]})
        self.assertEqual(
            SemanticRetriever(chunks, provider).search("query", k=3), ["pr:1", "pr:5", "pr:9"]
        )

    def test_truncates_to_k(self):
        chunks = [Chunk(f"pr:{i}", "pr", "common") for i in range(5)]
        provider = StaticEmbeddingProvider({"common": [1.0, 0.0], "query": [1.0, 0.0]})
        self.assertEqual(len(SemanticRetriever(chunks, provider).search("query", k=2)), 2)

    def test_empty_corpus_returns_empty(self):
        provider = StaticEmbeddingProvider({"query": [1.0, 0.0]})
        self.assertEqual(SemanticRetriever([], provider).search("query", k=3), [])

    def test_embeds_each_chunk_exactly_once_at_construction(self):
        calls = []

        def mapping(text):
            calls.append(text)
            return [1.0, 0.0]

        provider = StaticEmbeddingProvider(mapping)
        SemanticRetriever(self.chunks, provider)
        self.assertEqual(calls, [c.text for c in self.chunks])


if __name__ == "__main__":
    unittest.main()
