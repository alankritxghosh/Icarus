# demo/test_warm_cache.py
"""Proves demo.warm_cache (the Docker build-time warm-up) bakes a vector cache
the SERVER's runtime cold path accepts as a hit -- i.e. a warmed image really
does boot warm.

The always-run test proves the honest failure mode: with no embedder, warm()
fails loudly (SystemExit) rather than silently shipping a cold image. The live
test needs fastembed + the committed corpus and self-skips otherwise (mirrors
demo.test_semantic_wiring), building over a TEMP COPY of the corpus so nothing
writes vectors.json into the committed corpus dir."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from demo import library, warm_cache
from evals.vector_cache import corpus_fingerprint, load_vectors
from evals.corpus import load_chunks

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

CORPUS_DIR = Path(__file__).resolve().parent.parent / "evals" / "corpus"


def _reset_shared_embedder():
    library._embedder_state.clear()
    library._embedder_state.update(tried=False, provider=None)


class WarmCacheFailsLoudTests(unittest.TestCase):
    """No embedder -> the build step must FAIL, never silently ship a cold image."""

    def setUp(self):
        _reset_shared_embedder()
        self.addCleanup(_reset_shared_embedder)

    def test_raises_when_embedder_unavailable(self):
        with mock.patch.object(warm_cache, "_shared_embedder", return_value=None):
            with self.assertRaises(SystemExit):
                warm_cache.warm(CORPUS_DIR)


@unittest.skipUnless(_HAS_FASTEMBED and (CORPUS_DIR / "chunks.jsonl").exists(),
                     "needs fastembed and the committed corpus")
class WarmCacheLiveTests(unittest.TestCase):
    def setUp(self):
        _reset_shared_embedder()
        self.addCleanup(_reset_shared_embedder)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.corpus = Path(self._tmp.name)
        shutil.copy(CORPUS_DIR / "chunks.jsonl", self.corpus / "chunks.jsonl")

    def test_warm_writes_cache_runtime_accepts_as_a_hit(self):
        cache = warm_cache.warm(self.corpus)
        self.assertTrue(cache.exists())

        # The exact runtime check (demo.library._build_retriever -> load_vectors):
        # same model name + exactly the corpus's refs => a hit, so the server
        # skips the embed on boot.
        chunks = load_chunks(self.corpus / "chunks.jsonl")
        refs = [c.ref for c in chunks]
        model = library._shared_embedder().model_name
        # The same fingerprint the runtime path computes over this exact
        # corpus (evals.vector_cache.corpus_fingerprint, required since
        # c0c6fd1 -- a stale ref-only check let a re-ingested corpus with
        # rewritten text still report a cache HIT).
        cached = load_vectors(cache, model, refs, corpus_fingerprint(chunks))
        self.assertIsNotNone(cached, "runtime would MISS the baked cache and re-embed")
        self.assertEqual(set(cached.keys()), set(refs))


if __name__ == "__main__":
    unittest.main()
