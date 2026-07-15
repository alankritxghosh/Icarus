# demo/library.py
"""The demo's active-repo state: which corpus is loaded, its pipeline, and the
status of switching to another repo.

One active repo at a time. The built-in `simonw/llm` uses the committed corpus;
any other public repo is ingested once into a git-ignored cache and reused after.
A lock guards the swap so /ask always sees a consistent pipeline; during a slow
ingest the previous repo stays answerable (status just reads "indexing").
"""

import logging
import sys
import threading
from pathlib import Path

from evals.corpus import load_chunks
from evals.corpus_meta import load_meta
from evals.retriever import LexicalRetriever, SemanticRetriever, HybridRetriever
from evals.provider import make_provider
from evals.pipeline import GatedPipeline
from evals.ingest import ingest_repo

_log = logging.getLogger(__name__)

# Bounds a cold embed's wall-clock time (see evals/retriever.py's
# SemanticRetriever._embed_all). A CPU-throttled host can be slow enough that
# an unbounded embed loop hangs with no signal either way -- this happened for
# real (docs/HANDOFF.md): a private-repo connect on Render's free tier ran 35+
# minutes with zero visibility. Generous on purpose (not the shortest bound
# that "should" be enough) since we have no confirmed data point yet for how
# slow that tier really is; the point is BOUNDED and OBSERVABLE, not fast.
_EMBED_TIMEOUT_SECONDS = 900


def _log_embed_progress(done, total):
    # ~10 log lines regardless of corpus size, so a slow embed shows real
    # forward progress in the server's logs instead of total silence.
    step = max(1, total // 10)
    if done == total or done % step == 0:
        _log.info("embedding chunk %d/%d", done, total)


# The local embedding model is loaded ONCE per process and shared across every
# repo/pipeline (loading it is the expensive part; a query embed is cheap). If
# fastembed or the model is unavailable, retrieval degrades to lexical-only
# rather than crashing -- the demo still works, just without semantic recall.
_embedder_lock = threading.Lock()
_embedder_state = {"tried": False, "provider": None}


def _shared_embedder():
    with _embedder_lock:
        if _embedder_state["tried"]:
            return _embedder_state["provider"]
        _embedder_state["tried"] = True
        try:
            from evals.provider import LocalEmbeddingProvider
            _embedder_state["provider"] = LocalEmbeddingProvider()
        except Exception as e:  # fastembed missing / model load failed
            _log.warning(
                "local embedder unavailable (%s); using lexical-only retrieval",
                type(e).__name__,
            )
            _embedder_state["provider"] = None
        return _embedder_state["provider"]


def _build_retriever(chunks, corpus_dir, fast=False):
    """Hybrid (BM25 + local semantic) retrieval when the embedder is available,
    else lexical-only. Chunk embeddings are read from / written to an on-disk
    cache under `corpus_dir` so a server restart or repo reconnect doesn't
    re-embed the whole corpus (the query is still embedded live).

    `fast=True` skips the embedder entirely and returns lexical-only,
    unconditionally -- used for Library.connect_sync's fast first stage (see
    its docstring) so a fresh, uncached repo is searchable within seconds
    regardless of how slow the host's embedder is, instead of blocking on a
    cold embed that a CPU-throttled host can take many minutes -- or, proven
    live, never finish inside a bounded timeout at all -- to complete."""
    lexical = LexicalRetriever(chunks)
    if fast:
        return lexical
    embedder = _shared_embedder()
    if embedder is None:
        return lexical
    from evals.vector_cache import load_vectors, save_vectors
    model = getattr(embedder, "model_name", "unknown")
    cache_path = Path(corpus_dir) / "vectors.json"
    refs = [c.ref for c in chunks]
    cached = load_vectors(cache_path, model, refs)
    if cached is not None:
        semantic = SemanticRetriever(chunks, embedder, vectors=cached)
    else:
        semantic = SemanticRetriever(  # embeds every chunk now
            chunks, embedder,
            timeout=_EMBED_TIMEOUT_SECONDS,
            on_progress=_log_embed_progress,
        )
        save_vectors(cache_path, model, semantic.vectors)
    return HybridRetriever(lexical, semantic)


def _build_gated_pipeline(corpus_dir, fast=False):
    """Build the one trust-checked writer pipeline; `fast` changes retrieval only."""
    from evals.trust import assert_safe_for_private
    provider = make_provider("gemini-paid")
    assert_safe_for_private(provider)
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(_build_retriever(chunks, corpus_dir, fast=fast), chunks, provider)


_default_build_pipeline = _build_gated_pipeline


def _slug(repo):
    return repo.replace("/", "__")


class Library:
    def __init__(self, default_corpus_dir, cache_root, default_repo,
                 build_pipeline=_default_build_pipeline, ingest_fn=ingest_repo):
        self._default_dir = Path(default_corpus_dir)
        self._cache_root = Path(cache_root)
        self._default_repo = default_repo
        self._build_pipeline = build_pipeline
        self._ingest_fn = ingest_fn
        self._lock = threading.Lock()
        self._inflight = set()  # repos currently indexing (single-flight guard)
        # Prevent a stale background upgrade from replacing a newer connection.
        self._generation = 0
        self._status = "idle"
        self._error = None
        # Human-readable phase shown while a connect is in flight, so the app's
        # progress line says WHAT is happening instead of a silent spinner.
        # None when there's nothing in progress (idle/fully-ready/error).
        self._phase = None
        meta = load_meta(self._default_dir / "meta.json") or {}
        self._repo = meta.get("repo", default_repo)
        self._commit = meta.get("commit", "")
        self._counts = meta.get("counts")
        self._pipeline = self._build_pipeline(self._default_dir)
        self._status = "ready"

    def _resolve(self, repo):
        """-> (corpus_dir, needs_ingest)."""
        if repo == self._default_repo:
            return self._default_dir, False
        cache = self._cache_root / _slug(repo)
        return cache, not (cache / "chunks.jsonl").exists()

    def connect_sync(self, repo, background_upgrade=False):
        """Ingest/cache a repo, publish lexical search, then upgrade to semantic.

        Stage-2 failure leaves lexical search usable and a stale upgrade cannot
        replace a newer connection. Background upgrade requires a warm replica."""
        repo = (repo or "").strip()
        corpus_dir, needs_ingest = self._resolve(repo)
        with self._lock:
            already_indexing = repo in self._inflight
            if not already_indexing:
                self._inflight.add(repo)
        if already_indexing:
            return self.status_snapshot()  # already indexing this repo (single-flight)
        try:
            if needs_ingest:
                with self._lock:
                    self._status, self._error = "indexing", None
                    self._phase = "Reading the repository…"
                # Switched repos don't share simonw/llm's `llm/` package layout,
                # so glob the whole repo for code (the CLI keeps `llm` as default).
                self._ingest_fn(repo, corpus_dir, code_dir=".")
            meta = load_meta(Path(corpus_dir) / "meta.json") or {}
            connected_repo = meta.get("repo", repo)

            # STAGE 1 -- fast, lexical-only; publishes "ready" immediately.
            fast_pipeline = self._build_pipeline(corpus_dir, fast=True)
            with self._lock:
                self._pipeline = fast_pipeline
                self._repo = connected_repo
                self._commit = meta.get("commit", "")
                self._counts = meta.get("counts")
                self._status, self._error = "ready", None
                # Ready to search NOW (lexical); stage 2 upgrades to semantic in
                # the background. The phase says so honestly -- the repo is
                # usable, and getting smarter -- until _upgrade_to_semantic clears it.
                self._phase = "Building smart search…"
                self._generation += 1
                my_gen = self._generation
                # Ready means stage 1 is usable; do not block reconnect on stage 2.
                self._inflight.discard(repo)

            # STAGE 2 -- upgrade to hybrid/semantic; never undo stage 1.
            if background_upgrade:
                threading.Thread(
                    target=self._upgrade_to_semantic,
                    args=(corpus_dir, connected_repo, my_gen),
                    daemon=True,
                ).start()
            else:
                self._upgrade_to_semantic(corpus_dir, connected_repo, my_gen)
        except Exception as e:  # keep the previous repo answerable; never leak internals
            print(f"connect failed for {repo!r} ({type(e).__name__})", file=sys.stderr)
            with self._lock:
                self._status = "error"
                self._phase = None
                self._error = "Couldn't index that repo. Check it's a public owner/name and try again."
        finally:
            # Backstop for failure before stage 1 released the slot.
            with self._lock:
                self._inflight.discard(repo)
        return self.status_snapshot()

    def _upgrade_to_semantic(self, corpus_dir, connected_repo, generation):
        """Install semantic search if this is still the newest connection."""
        try:
            full_pipeline = self._build_pipeline(corpus_dir)
            with self._lock:
                if self._generation == generation:  # still the latest connect
                    self._pipeline = full_pipeline
                    self._phase = None  # smart search ready; nothing pending
        except Exception as e:
            print(
                f"semantic upgrade failed for {connected_repo!r} "
                f"({type(e).__name__}); staying on lexical-only search",
                file=sys.stderr,
            )
            with self._lock:
                if self._generation == generation:
                    self._phase = None  # gave up on the upgrade; lexical stays, nothing pending

    def current_pipeline(self):
        with self._lock:
            return self._pipeline

    def provenance(self):
        with self._lock:
            return self._repo, self._commit

    def status_snapshot(self):
        with self._lock:
            return {"state": self._status, "repo": self._repo, "commit": self._commit,
                    "counts": self._counts, "error": self._error, "phase": self._phase}
