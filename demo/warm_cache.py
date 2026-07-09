# demo/warm_cache.py
"""Build-time warm-up: bake the default corpus's embedding cache -- and, as a
side effect, the local fastembed model -- into the container image so a cold
Render deploy boots WARM instead of blocking on a from-scratch embed of the whole
corpus (docs/HANDOFF.md §4: every fresh deploy/restart/idle-sleep wiped the
git-ignored vectors.json and had to re-embed all 243 default chunks, which kept
the service stuck in "starting up").

Run ONCE during `docker build` (see the Dockerfile). It builds the SAME hybrid
retriever the server builds at runtime, via demo.library._build_retriever, so the
vectors.json it writes to evals/corpus/ is exactly the cache the server's own
cold path would have produced -- runtime then hits evals.vector_cache.load_vectors
and skips the embed entirely. FASTEMBED_CACHE_PATH (set in the Dockerfile) pins
the model download to a stable in-image path shared by build and runtime.

Pure optimization: if this step is removed, the server still works -- it just
falls back to the slow cold start it had before. The step fails LOUDLY (non-zero
exit) if the embedder is unavailable or no cache lands, so a broken warm-up fails
the image build instead of silently shipping a cold container.
"""

from pathlib import Path

from evals.corpus import load_chunks
from demo.library import _build_retriever, _shared_embedder

CORPUS_DIR = Path(__file__).resolve().parent.parent / "evals" / "corpus"


def warm(corpus_dir: Path = CORPUS_DIR) -> Path:
    """Embed the default corpus and write its vectors.json cache. Returns the
    cache path. Raises SystemExit (fails the build) if fastembed is unavailable
    or the cache did not land."""
    if _shared_embedder() is None:
        raise SystemExit(
            "warm_cache: local embedder unavailable (fastembed not importable); "
            "cannot bake the embedding cache"
        )
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    # Side effect: embeds every chunk and writes vectors.json under corpus_dir.
    _build_retriever(chunks, corpus_dir)
    cache = Path(corpus_dir) / "vectors.json"
    if not cache.exists():
        raise SystemExit(f"warm_cache: expected cache not written at {cache}")
    return cache


if __name__ == "__main__":
    cache = warm()
    print(f"warm_cache: baked embedding cache at {cache} ({cache.stat().st_size} bytes)")
