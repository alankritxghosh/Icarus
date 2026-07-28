# evals/test_vector_cache.py
"""The embedding cache: round-trips, and fails safe to None (re-embed) on every
mismatch/corruption so caching can never change what is retrieved."""

import json
import tempfile
import unittest
from pathlib import Path

from evals.corpus import Chunk
from evals.retriever import SemanticRetriever
from evals.provider import StaticEmbeddingProvider
from evals.vector_cache import corpus_fingerprint, load_vectors, save_vectors


class VectorCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vectors.json"
        self.refs = ["code:a#L1-L2", "code:b#L1-L2"]
        self.vectors = {"code:a#L1-L2": [1.0, 0.0], "code:b#L1-L2": [0.0, 1.0]}
        self.chunks = [Chunk("code:a#L1-L2", "code", "alpha"),
                       Chunk("code:b#L1-L2", "code", "beta")]
        self.fp = corpus_fingerprint(self.chunks)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_then_load_round_trips(self):
        save_vectors(self.path, "modelX", self.vectors, self.fp)
        got = load_vectors(self.path, "modelX", self.refs, self.fp)
        self.assertEqual(got, self.vectors)

    def test_missing_file_returns_none(self):
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs, self.fp))

    def test_model_mismatch_returns_none(self):
        save_vectors(self.path, "modelX", self.vectors, self.fp)
        self.assertIsNone(load_vectors(self.path, "modelY", self.refs, self.fp))  # model changed

    def test_ref_set_mismatch_returns_none(self):
        save_vectors(self.path, "modelX", self.vectors, self.fp)
        # corpus changed: an extra ref not in the cache -> miss, re-embed
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs + ["code:c#L1-L2"], self.fp))
        # ...and a missing ref (cache has an extra) also -> miss
        self.assertIsNone(load_vectors(self.path, "modelX", ["code:a#L1-L2"], self.fp))

    def test_corrupt_file_returns_none_not_raise(self):
        self.path.write_text("{not valid json")
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs, self.fp))


class SemanticRetrieverVectorsParamTests(unittest.TestCase):
    def test_provided_vectors_skip_chunk_embedding(self):
        chunks = [Chunk("code:a#L1-L2", "code", "alpha"), Chunk("code:b#L1-L2", "code", "beta")]
        vectors = {"code:a#L1-L2": [1.0, 0.0], "code:b#L1-L2": [0.0, 1.0]}
        calls = []

        def embed(text):
            calls.append(text)
            return [1.0, 0.0]  # only ever the query

        provider = StaticEmbeddingProvider(embed)
        r = SemanticRetriever(chunks, provider, vectors=vectors)
        # No chunk was embedded at construction (vectors were supplied)...
        self.assertEqual(calls, [])
        self.assertEqual(r.vectors, vectors)
        # ...but the query IS embedded live at search time.
        r.search("some query", 5)
        self.assertEqual(calls, ["some query"])

    def test_without_vectors_embeds_every_chunk(self):
        chunks = [Chunk("code:a#L1-L2", "code", "alpha"), Chunk("code:b#L1-L2", "code", "beta")]
        embedded = []
        provider = StaticEmbeddingProvider(lambda t: (embedded.append(t), [1.0, 0.0])[1])
        SemanticRetriever(chunks, provider)
        self.assertEqual(set(embedded), {"alpha", "beta"})

    def test_incomplete_vectors_raise_at_construction_not_query_time(self):
        # A vectors= that doesn't cover every chunk ref must fail LOUD at build,
        # not KeyError later at search() time.
        chunks = [Chunk("code:a#L1-L2", "code", "alpha"), Chunk("code:b#L1-L2", "code", "beta")]
        provider = StaticEmbeddingProvider(lambda t: [1.0, 0.0])
        with self.assertRaises(ValueError):
            SemanticRetriever(chunks, provider, vectors={"code:a#L1-L2": [1.0, 0.0]})


if __name__ == "__main__":
    unittest.main()


class CorpusContentInvalidationTests(unittest.TestCase):
    """The gap that made a re-ingest serve stale embeddings (found 2026-07-28).

    A refreshed corpus at the SAME commit keeps every ref and rewrites the text
    -- which is exactly what happened when PR/issue chunks gained their
    discussion. Ref coverage still matched, so the cache reported a hit and
    semantic ranking was computed from vectors of text that no longer existed.
    Groundedness was never at risk; retrieval quality silently was."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "vectors.json"
        self.old = [Chunk("pr:1", "pr", "PR #1: Add retries"),
                    Chunk("pr:2", "pr", "PR #2: Fix timeout")]
        # Same refs, richer text -- a discussion-bearing re-ingest.
        self.new = [Chunk("pr:1", "pr", "PR #1: Add retries\n\nComment by dev: capped at 3"),
                    Chunk("pr:2", "pr", "PR #2: Fix timeout\n\nComment by dev: 30s was arbitrary")]
        self.refs = [c.ref for c in self.old]
        self.vectors = {"pr:1": [1.0, 0.0], "pr:2": [0.0, 1.0]}

    def test_same_refs_but_changed_text_is_a_cache_MISS(self):
        save_vectors(self.path, "m", self.vectors, corpus_fingerprint(self.old))
        self.assertEqual(set(c.ref for c in self.old), set(c.ref for c in self.new),
                         "the refs must be identical, or this proves nothing")
        self.assertIsNone(
            load_vectors(self.path, "m", self.refs, corpus_fingerprint(self.new)),
            "changed chunk TEXT must invalidate the cache even when refs match")

    def test_unchanged_corpus_is_still_a_cache_HIT(self):
        # The whole point of the cache: an untouched corpus must not re-embed.
        save_vectors(self.path, "m", self.vectors, corpus_fingerprint(self.old))
        self.assertEqual(
            load_vectors(self.path, "m", self.refs, corpus_fingerprint(self.old)),
            self.vectors)

    def test_a_pre_fingerprint_cache_misses_rather_than_being_trusted(self):
        # Caches written before this existed (including any already on the
        # deployed volume) carry no fingerprint and cannot be validated.
        self.path.write_text(json.dumps({"model": "m", "vectors": self.vectors}))
        self.assertIsNone(load_vectors(self.path, "m", self.refs,
                                       corpus_fingerprint(self.old)))

    def test_fingerprint_is_deterministic_across_calls(self):
        self.assertEqual(corpus_fingerprint(self.old), corpus_fingerprint(self.old))

    def test_reordering_the_corpus_changes_the_fingerprint(self):
        self.assertNotEqual(corpus_fingerprint(self.old),
                            corpus_fingerprint(list(reversed(self.old))))

    def test_a_ref_and_text_swap_is_not_confused_for_the_same_corpus(self):
        # Naive concatenation would hash "pr:1"+"a" and "pr:1a"+"" alike; the
        # NUL separators are what stop that.
        a = [Chunk("pr:1", "pr", "a")]
        b = [Chunk("pr:1a", "pr", "")]
        self.assertNotEqual(corpus_fingerprint(a), corpus_fingerprint(b))

    def test_an_empty_corpus_hashes_without_raising(self):
        self.assertIsInstance(corpus_fingerprint([]), str)
