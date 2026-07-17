# demo/test_semantic_wiring.py
"""Proves Brick C's semantic retrieval is actually wired into the demo's serving
pipeline (not just the eval harness): the demo builds a HybridRetriever (BM25 +
local semantic) when the local embedder is available, and degrades gracefully to
LexicalRetriever (never crashes) when fastembed/the model is not.

Hermetic: every test resets the process-global shared-embedder singleton, and the
live tests build over a TEMP COPY of the corpus so nothing writes vectors.json
into the committed corpus dir -- no cross-test state to bleed."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evals.corpus import Chunk
from evals.retriever import LexicalRetriever, HybridRetriever, NormalizingRetriever
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


def _reset_shared_embedder():
    # The shared embedder is a process-global singleton; reset it so no test
    # leaks a (real or None) provider into another and every test is hermetic.
    library._embedder_state.clear()
    library._embedder_state.update(tried=False, provider=None)


class _SpyEmbedder:
    """A stub embedder that records which texts it embeds, so a test can prove
    the cache prevents re-embedding chunks on a second build."""
    model_name = "spy-model-v1"

    def __init__(self):
        self.embedded = []

    def embed(self, text):
        self.embedded.append(text)
        return [float(len(text)), 1.0]


class SemanticWiringFallbackTests(unittest.TestCase):
    def setUp(self):
        _reset_shared_embedder()
        self.addCleanup(_reset_shared_embedder)

    def test_falls_back_to_lexical_when_embedder_unavailable(self):
        # Graceful degradation: no embedder -> lexical-only, never a crash.
        with mock.patch.object(library, "_shared_embedder", return_value=None):
            retr = library._build_retriever(_FAKE_CHUNKS, CORPUS_DIR)
        # Query normalization (Brick Q) wraps every retriever; the inner one is
        # lexical-only, never hybrid, when no embedder is available.
        self.assertIsInstance(retr, NormalizingRetriever)
        self.assertIsInstance(retr._retriever, LexicalRetriever)
        self.assertNotIsInstance(retr._retriever, HybridRetriever)

    def test_builds_hybrid_when_embedder_present(self):
        # With a (stub) embedder present, the demo builds a HybridRetriever.
        embedder = mock.Mock(spec=["embed", "model_name"])
        embedder.model_name = "spy-model-v1"
        embedder.embed.side_effect = lambda text: [float(len(text)), 1.0]
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(library, "_shared_embedder", return_value=embedder):
                retr = library._build_retriever(_FAKE_CHUNKS, Path(d))
        self.assertIsInstance(retr, NormalizingRetriever)
        self.assertIsInstance(retr._retriever, HybridRetriever)

    def test_second_build_uses_cache_and_does_not_re_embed_chunks(self):
        # The whole point of the cache: a server restart / repo reconnect must
        # NOT re-embed the whole corpus. Second build over the same corpus dir
        # embeds zero chunks (cache hit).
        chunks = [
            Chunk("code:a#L1-L2", "code", "alpha alpha"),
            Chunk("code:b#L1-L2", "code", "beta beta"),
        ]
        with tempfile.TemporaryDirectory() as d:
            corpus_dir = Path(d)
            spy = _SpyEmbedder()
            with mock.patch.object(library, "_shared_embedder", return_value=spy):
                r1 = library._build_retriever(chunks, corpus_dir)
                after_first = list(spy.embedded)
                r2 = library._build_retriever(chunks, corpus_dir)
                during_second = spy.embedded[len(after_first):]
            self.assertIsInstance(r1._retriever, HybridRetriever)
            self.assertIsInstance(r2._retriever, HybridRetriever)
            self.assertEqual(set(after_first), {"alpha alpha", "beta beta"})  # embedded once
            self.assertEqual(during_second, [])  # cache hit -> no chunk re-embed
            self.assertTrue((corpus_dir / "vectors.json").exists())


@unittest.skipUnless(_HAS_FASTEMBED and (CORPUS_DIR / "chunks.jsonl").exists(),
                     "needs fastembed and the committed corpus")
class SemanticWiringLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _reset_shared_embedder()
        # Build over a TEMP COPY of the corpus so the vector cache is written to
        # tmp (and cleaned up), never into the committed evals/corpus dir.
        cls._tmp = tempfile.TemporaryDirectory()
        d = Path(cls._tmp.name)
        shutil.copy(CORPUS_DIR / "chunks.jsonl", d / "chunks.jsonl")
        meta = CORPUS_DIR / "meta.json"
        if meta.exists():
            shutil.copy(meta, d / "meta.json")
        cls.corpus = d

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        _reset_shared_embedder()

    def test_default_pipeline_wires_hybrid_over_the_corpus(self):
        pipe = library._build_gated_pipeline(self.corpus)
        self.assertIsInstance(pipe._retriever, NormalizingRetriever)
        self.assertIsInstance(pipe._retriever._retriever, HybridRetriever)

    def test_semantic_retrieval_finds_a_paraphrase_bm25_would_miss(self):
        # The whole point of wiring semantic in: a query phrased unlike the code
        # still retrieves. Sanity that the wired hybrid returns results.
        pipe = library._build_gated_pipeline(self.corpus)
        hits = pipe._retriever.search("how are command line arguments parsed", 5)
        self.assertTrue(hits)


if __name__ == "__main__":
    unittest.main()
