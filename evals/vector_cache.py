# evals/vector_cache.py
"""On-disk cache of chunk embeddings, so the demo server doesn't re-embed a whole
corpus on every start / repo reconnect.

The cache is a JSON sidecar tagged with the model name. It is treated as a pure
optimization: a miss, a model change, a corpus change, or any read/write error
falls back to re-embedding -- caching never changes what gets retrieved, only how
fast the retriever is built. The cache is derived data (model-specific), so it is
git-ignored and regenerated on demand, never committed.
"""

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def load_vectors(path, model_name, refs):
    """Return the cached {ref: vector} ONLY if the cache at `path` was written by
    the same `model_name` AND covers exactly `refs`; otherwise None so the caller
    re-embeds. Fail-safe: a missing/corrupt/mismatched cache returns None, never
    raises."""
    try:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        if data.get("model") != model_name:
            return None  # model changed -> old vectors are meaningless
        vectors = data.get("vectors")
        if not isinstance(vectors, dict) or set(vectors.keys()) != set(refs):
            return None  # corpus changed -> coverage no longer matches
        return vectors
    except Exception as e:
        _log.warning("vector cache read failed (%s); will re-embed", type(e).__name__)
        return None


def save_vectors(path, model_name, vectors):
    """Write the cache atomically (temp file + replace). Best-effort: a write
    failure is logged and swallowed -- caching must never break serving -- but it
    is NOT hidden (logged, and the caller has the vectors in memory regardless)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps({"model": model_name, "vectors": vectors}))
        tmp.replace(p)
    except Exception as e:
        _log.warning("vector cache write failed (%s); continuing without cache", type(e).__name__)
