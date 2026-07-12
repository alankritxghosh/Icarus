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
from evals.provider import make_provider, has_provider_key
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


def _pick_writer():
    return "groq" if has_provider_key("groq") else "gemini" if has_provider_key("gemini") else "openrouter"


def _default_build_pipeline(corpus_dir, fast=False):
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(_build_retriever(chunks, corpus_dir, fast=fast), chunks, make_provider(_pick_writer()))


def _default_build_private_pipeline(corpus_dir, fast=False):
    # The interlock is checked at construction -- the single chokepoint where
    # the provider is fixed for this pipeline's lifetime. Applies identically
    # regardless of `fast` -- fast only changes which RETRIEVER gets built,
    # never the writer/trust decision.
    from evals.trust import assert_safe_for_private
    provider = make_provider("gemini-paid")
    assert_safe_for_private(provider)
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(_build_retriever(chunks, corpus_dir, fast=fast), chunks, provider)


def _default_private_ready():
    return has_provider_key("gemini-paid")


def _slug(repo):
    return repo.replace("/", "__")


class Library:
    def __init__(self, default_corpus_dir, cache_root, default_repo,
                 build_pipeline=_default_build_pipeline, ingest_fn=ingest_repo,
                 build_private_pipeline=_default_build_private_pipeline,
                 private_ready=_default_private_ready):
        self._default_dir = Path(default_corpus_dir)
        self._cache_root = Path(cache_root)
        self._default_repo = default_repo
        self._build_pipeline = build_pipeline
        self._ingest_fn = ingest_fn
        self._build_private_pipeline = build_private_pipeline
        self._private_ready = private_ready
        self._private = False  # is the CURRENTLY connected repo private?
        self._private_root = Path(cache_root).parent / "private"
        self._lock = threading.Lock()
        self._inflight = set()  # repos currently indexing (single-flight guard)
        # Monotonic connect id. Every connect bumps it (under _lock at stage 1);
        # a background stage-2 upgrade only installs if it is still the latest,
        # so a slow stage-2 from an EARLIER connect can't clobber a newer one --
        # matters under Option B, where connect_sync returns while stage 2 is
        # still running, so two connects to the SAME repo can overlap (the repo
        # name alone can't tell their pipelines apart).
        self._generation = 0
        self._status = "idle"
        self._error = None
        meta = load_meta(self._default_dir / "meta.json") or {}
        self._repo = meta.get("repo", default_repo)
        self._commit = meta.get("commit", "")
        self._counts = meta.get("counts")
        self._pipeline = self._build_pipeline(self._default_dir)
        self._status = "ready"

    def _cache_dir(self, repo):
        return self._cache_root / _slug(repo)

    def _resolve(self, repo, private=False):
        """-> (corpus_dir, needs_ingest)."""
        if repo == self._default_repo:
            return self._default_dir, False
        base = self._private_root if private else self._cache_root
        cache = base / _slug(repo)
        return cache, not (cache / "chunks.jsonl").exists()

    def connect_sync(self, repo, token=None, private=False, background_upgrade=False):
        """Switch the active repo (blocking, from the caller's own thread --
        demo/server.py backgrounds the whole call so the HTTP request itself
        never blocks). Ingests on a cache miss, then connects in TWO STAGES:

        STAGE 1 builds a fast, lexical-only (BM25) pipeline and publishes it
        immediately -- searchable within seconds regardless of corpus size or
        how slow the host's embedder is. This exists because of a real,
        live-confirmed incident: a CPU-throttled free-tier host (0.1 CPU) ran
        a 216-chunk private-repo connect's embed step for the full 15-minute
        bounded timeout without embedding even 10% of the corpus -- the repo
        was simply never usable (see docs/HANDOFF.md). Lexical-only is a real,
        already-supported retrieval mode (the same fallback used when no
        embedder is available at all), not a stub.

        STAGE 2 then builds the full hybrid (lexical + semantic) pipeline and
        upgrades to it if/when the embed finishes. A slow host or a timeout
        there is NOT a connect failure -- the repo is already answerable via
        stage 1 -- so stage 2's own exceptions are caught and logged, never
        propagated. The upgrade only applies if the caller hasn't switched to
        a different repo in the meantime (checked under the lock).

        On a genuine STAGE 1 failure (bad repo, ingest failure, a refused
        private connect) the previous repo stays active; status becomes
        'error'.

        `background_upgrade=True` returns as soon as STAGE 1 has published a
        usable (lexical) pipeline and runs STAGE 2 on a daemon thread instead of
        inline (Option B). On request-scoped-CPU hosts (Azure Container Apps,
        Cloud Run) a blocking sync connect holds the HTTP request open through
        the whole embed, which a large repo can run past the platform's ingress
        timeout (Azure: a hard 240s), killing the connect. Backgrounding STAGE 2
        frees the request from the multi-minute embed -- but the embed then needs
        a container that stays alive after the response returns, so this is safe
        only when a replica is kept warm (min-replicas>=1); with scale-to-zero
        the backgrounded embed can be CPU-starved, so keep it inline (default).

        `token` (the caller's own GitHub token, when connecting a private repo)
        is a LOCAL VARIABLE ONLY -- never stored on self, never logged, never
        included in any error/status output."""
        repo = (repo or "").strip()
        if private and not self._private_ready():
            with self._lock:
                self._status = "error"
                self._error = "Private repos aren't available yet on this brain."
            return self.status_snapshot()
        corpus_dir, needs_ingest = self._resolve(repo, private)
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
                # Switched repos don't share simonw/llm's `llm/` package layout,
                # so glob the whole repo for code (the CLI keeps `llm` as default).
                self._ingest_fn(repo, corpus_dir, code_dir=".", token=token)
            build_pipeline = self._build_private_pipeline if private else self._build_pipeline
            meta = load_meta(Path(corpus_dir) / "meta.json") or {}
            connected_repo = meta.get("repo", repo)

            # STAGE 1 -- fast, lexical-only; publishes "ready" immediately.
            fast_pipeline = build_pipeline(corpus_dir, fast=True)
            with self._lock:
                self._pipeline = fast_pipeline
                self._repo = connected_repo
                self._commit = meta.get("commit", "")
                self._counts = meta.get("counts")
                self._private = private
                self._status, self._error = "ready", None
                # This connect's id. Stage 2 below only installs its pipeline if
                # this is still the latest connect (see _upgrade_to_semantic), so
                # a slower stage 2 from an EARLIER overlapping connect can't
                # clobber a newer one.
                self._generation += 1
                my_gen = self._generation
                # Release the single-flight slot HERE, the moment the repo is
                # genuinely usable -- NOT in the outer `finally` after stage 2.
                # Holding it through the (potentially long/slow) semantic upgrade
                # made a reconnect to this same repo hit `already_indexing` and
                # get silently swallowed while an old upgrade was still finishing,
                # leaving a polling client stuck forever (docs/HANDOFF.md §6, P1).
                # Stage 2 below runs unguarded; a reconnect re-runs the cheap
                # cache-hit stage 1 rather than being blocked.
                self._inflight.discard(repo)

            # STAGE 2 -- upgrade to hybrid/semantic; never undoes stage 1. Run it
            # inline (default) or, when background_upgrade is set, on a daemon
            # thread so the caller (an HTTP request) is freed the moment stage 1
            # is usable -- see the connect_sync docstring for when each is safe.
            if background_upgrade:
                threading.Thread(
                    target=self._upgrade_to_semantic,
                    args=(build_pipeline, corpus_dir, connected_repo, my_gen),
                    daemon=True,
                ).start()
            else:
                self._upgrade_to_semantic(build_pipeline, corpus_dir, connected_repo, my_gen)
        except Exception:  # keep the previous repo answerable; never leak internals
            with self._lock:
                self._status = "error"
                self._error = "Couldn't index that repo. Check it's a public owner/name and try again."
        finally:
            # Backstop for the FAILURE paths (an ingest/stage-1 error before the
            # discard above). On the success path the slot is already released
            # after stage 1; discard is idempotent, so this is a harmless no-op.
            with self._lock:
                self._inflight.discard(repo)
        return self.status_snapshot()

    def _upgrade_to_semantic(self, build_pipeline, corpus_dir, connected_repo, generation):
        """STAGE 2: build the full hybrid (lexical + semantic) pipeline and swap
        it in -- unless a newer connect has happened since (checked by generation
        under the lock). Guarding on the generation, not just the repo name, is
        what makes an A->B->A reconnect safe under Option B: a stale stage 2 from
        the first A connect has an older generation than the second A connect, so
        it won't overwrite the newer pipeline (the repo name is 'A' for both).
        A slow host or an embed timeout here is NOT a connect failure: stage 1
        already made the repo answerable, so any exception is logged and
        swallowed, never undoing stage 1. Safe to run inline or on a daemon
        thread (see connect_sync's background_upgrade)."""
        try:
            full_pipeline = build_pipeline(corpus_dir)
            with self._lock:
                if self._generation == generation:  # still the latest connect
                    self._pipeline = full_pipeline
        except Exception as e:
            print(
                f"semantic upgrade failed for {connected_repo!r} "
                f"({type(e).__name__}); staying on lexical-only search",
                file=sys.stderr,
            )

    def current_pipeline(self):
        with self._lock:
            return self._pipeline

    def provenance(self):
        with self._lock:
            return self._repo, self._commit

    def status_snapshot(self):
        with self._lock:
            return {"state": self._status, "repo": self._repo, "commit": self._commit,
                    "counts": self._counts, "error": self._error, "private": self._private}
