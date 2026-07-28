# evals/vector_cache.py
"""On-disk cache of chunk embeddings, so the demo server doesn't re-embed a whole
corpus on every start / repo reconnect.

The cache is a JSON sidecar tagged with the model name. It is treated as a pure
optimization: a miss, a model change, a corpus change, or any read/write error
falls back to re-embedding -- caching never changes what gets retrieved, only how
fast the retriever is built. The cache is derived data (model-specific), so it is
git-ignored and regenerated on demand, never committed.
"""

import hashlib
import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def corpus_fingerprint(chunks) -> str:
    """A content hash of the corpus these vectors were computed FROM.

    Ref coverage alone is NOT enough, and the gap is silent. A re-ingested
    corpus at the same commit has the SAME refs with DIFFERENT text -- exactly
    what happened when PR/issue chunks gained their discussion (2026-07-28) --
    so a ref-only check happily reuses embeddings computed from text that no
    longer exists. Nothing about groundedness breaks (the writer is always
    shown the real current text), but RANKING would be computed from stale
    vectors: a retrieval regression that reports itself as a cache hit.

    Order-sensitive on purpose: ingest is deterministic, so a reordered corpus
    is a changed corpus, and re-embedding it is the safe, cheap direction.

    Cost is ~0.1s per 100MB against MINUTES to re-embed, so it is worth paying
    on every load rather than trusting a weaker proxy such as chunk count or
    text length.
    """
    h = hashlib.sha256()
    for c in chunks:
        h.update((getattr(c, "ref", "") or "").encode("utf-8", "replace"))
        h.update(b"\x00")
        h.update((getattr(c, "text", "") or "").encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()


def load_vectors(path, model_name, refs, fingerprint):
    """Return the cached {ref: vector} ONLY if the cache at `path` was written by
    the same `model_name`, from the same corpus CONTENT (`fingerprint`), AND
    covers exactly `refs`; otherwise None so the caller re-embeds. Fail-safe: a
    missing/corrupt/mismatched cache returns None, never raises.

    `fingerprint` is required rather than optional: an optional one would let a
    caller silently opt back into the ref-only check that made this cache serve
    stale vectors in the first place. A cache written before fingerprints
    existed has no such key, so it misses and re-embeds -- the safe direction.
    """
    try:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        if data.get("model") != model_name:
            return None  # model changed -> old vectors are meaningless
        if data.get("fingerprint") != fingerprint:
            return None  # corpus TEXT changed (or a pre-fingerprint cache)
        vectors = data.get("vectors")
        if not isinstance(vectors, dict) or set(vectors.keys()) != set(refs):
            return None  # corpus changed -> coverage no longer matches
        return vectors
    except Exception as e:
        _log.warning("vector cache read failed (%s); will re-embed", type(e).__name__)
        return None


def save_vectors(path, model_name, vectors, fingerprint):
    """Write the cache atomically (temp file + replace). Best-effort: a write
    failure is logged and swallowed -- caching must never break serving -- but it
    is NOT hidden (logged, and the caller has the vectors in memory regardless)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps({"model": model_name, "fingerprint": fingerprint,
                                   "vectors": vectors}))
        tmp.replace(p)
    except Exception as e:
        _log.warning("vector cache write failed (%s); continuing without cache", type(e).__name__)
