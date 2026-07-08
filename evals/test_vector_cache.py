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
from evals.vector_cache import load_vectors, save_vectors


class VectorCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vectors.json"
        self.refs = ["code:a#L1-L2", "code:b#L1-L2"]
        self.vectors = {"code:a#L1-L2": [1.0, 0.0], "code:b#L1-L2": [0.0, 1.0]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_then_load_round_trips(self):
        save_vectors(self.path, "modelX", self.vectors)
        got = load_vectors(self.path, "modelX", self.refs)
        self.assertEqual(got, self.vectors)

    def test_missing_file_returns_none(self):
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs))

    def test_model_mismatch_returns_none(self):
        save_vectors(self.path, "modelX", self.vectors)
        self.assertIsNone(load_vectors(self.path, "modelY", self.refs))  # model changed

    def test_ref_set_mismatch_returns_none(self):
        save_vectors(self.path, "modelX", self.vectors)
        # corpus changed: an extra ref not in the cache -> miss, re-embed
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs + ["code:c#L1-L2"]))
        # ...and a missing ref (cache has an extra) also -> miss
        self.assertIsNone(load_vectors(self.path, "modelX", ["code:a#L1-L2"]))

    def test_corrupt_file_returns_none_not_raise(self):
        self.path.write_text("{not valid json")
        self.assertIsNone(load_vectors(self.path, "modelX", self.refs))


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


if __name__ == "__main__":
    unittest.main()
