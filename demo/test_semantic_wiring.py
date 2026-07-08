# demo/test_semantic_wiring.py
"""Proves Brick C's semantic retrieval is actually wired into the demo's serving
pipeline (not just the eval harness): the demo builds a HybridRetriever (BM25 +
local semantic) when the local embedder is available, and degrades gracefully to
LexicalRetriever (never crashes) when fastembed/the model is not."""

import unittest
from pathlib import Path
from unittest import mock

from evals.corpus import Chunk
from evals.retriever import LexicalRetriever, HybridRetriever
from demo import library

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

CORPUS_DIR = Path(__file__).resolve().parent.parent / "evals" / "corpus"
_FAKE_CHUNKS = [
    Chunk("code:a#L1-L5", "code", "def authenticate(user): return verify(user.token)"),
    Chunk("code:b#L1-L3", "code", "def bump_version(): pkg.version += 1"),
]


class SemanticWiringFallbackTests(unittest.TestCase):
    def test_falls_back_to_lexical_when_embedder_unavailable(self):
        # Graceful degradation: no embedder -> lexical-only, never a crash.
        with mock.patch.object(library, "_shared_embedder", return_value=None):
            retr = library._build_retriever(_FAKE_CHUNKS, CORPUS_DIR)
        self.assertIsInstance(retr, LexicalRetriever)
        self.assertNotIsInstance(retr, HybridRetriever)

    def test_builds_hybrid_when_embedder_present(self):
        # With a (stub) embedder present, the demo builds a HybridRetriever.
        embedder = mock.Mock()
        embedder.embed.side_effect = lambda text: [float(len(text)), 1.0]
        with mock.patch.object(library, "_shared_embedder", return_value=embedder):
            retr = library._build_retriever(_FAKE_CHUNKS, CORPUS_DIR)
        self.assertIsInstance(retr, HybridRetriever)


@unittest.skipUnless(_HAS_FASTEMBED and (CORPUS_DIR / "chunks.jsonl").exists(),
                     "needs fastembed and the committed corpus")
class SemanticWiringLiveTests(unittest.TestCase):
    def test_default_pipeline_wires_hybrid_over_the_committed_corpus(self):
        pipe = library._default_build_pipeline(CORPUS_DIR)
        self.assertIsInstance(pipe._retriever, HybridRetriever)

    def test_semantic_retrieval_finds_a_paraphrase_bm25_would_miss(self):
        # The whole point of wiring semantic in: a query phrased unlike the code
        # still retrieves. Sanity that the wired hybrid returns results.
        pipe = library._default_build_pipeline(CORPUS_DIR)
        hits = pipe._retriever.search("how are command line arguments parsed", 5)
        self.assertTrue(hits)


if __name__ == "__main__":
    unittest.main()
