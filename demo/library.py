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
import time
from pathlib import Path

from evals.corpus import load_chunks
from evals.corpus_meta import load_meta
from evals.retriever import (
    LexicalRetriever, SemanticRetriever, HybridRetriever, NormalizingRetriever,
)
from evals.query_normalize import build_vocabulary
from evals.provider import make_provider
from evals.pipeline import GatedPipeline
from evals.ingest import ingest_repo

_log = logging.getLogger(__name__)

# Bounds a cold embed's wall-clock time (see evals/retriever.py's
# SemanticRetriever._embed_all) so a stuck embed can't hang forever with no
# signal -- BOUNDED and OBSERVABLE, not fast. But it must SCALE with corpus size:
# embedding is ~sequential and unbatched on purpose (fastembed's batch path pads
# every text in a batch to the longest one -- measured 3.3x SLOWER on real
# variable-length code, 2026-07-19), so a 50k-chunk repo legitimately takes ~an
# hour on the warm 2-CPU replica. A fixed 900s cap silently killed the BACKGROUND
# semantic embed of any big repo, leaving it stuck lexical-only (found live:
# huggingface/transformers, 50k chunks). Scale ~0.1s/chunk over a 900s floor:
# small/medium repos keep the same generous bound; a 50k repo gets ~83 min so its
# background embed can actually finish. Ceiling, not the expected time.
_EMBED_TIMEOUT_FLOOR_SECONDS = 900
_EMBED_SECONDS_PER_CHUNK = 0.1


def _embed_timeout(n_chunks):
    """Wall-clock ceiling for embedding `n_chunks`: a 900s floor, scaled up for
    large corpora so a big repo's background semantic embed isn't cut off."""
    return max(_EMBED_TIMEOUT_FLOOR_SECONDS, int(n_chunks * _EMBED_SECONDS_PER_CHUNK))


def _progress_reporter(on_progress):
    """Log progress as before, AND report it to the caller when one asked.

    Composed rather than replaced: the server log line is what diagnoses a
    stuck embed after the fact, and the status field is what a waiting user
    sees. Losing either to gain the other would be a bad trade."""
    if on_progress is None:
        return _log_embed_progress

    def report(done, total):
        _log_embed_progress(done, total)
        on_progress(done, total)
    return report


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


def _build_retriever(chunks, corpus_dir, fast=False, on_progress=None):
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
    # Brick Q: normalize the query (stdlib fuzzy spelling toward real corpus
    # terms) before it hits ANY retriever -- proven live to close messy-phrasing
    # recall@5 up to the clean baseline without regressing clean phrasing (see
    # evals/test_query_normalization_eval.py). Vocabulary is the corpus's own
    # tokens; only the SEARCH text is normalized, never what the writer sees.
    vocab = build_vocabulary(chunks)
    lexical = LexicalRetriever(chunks)
    if fast:
        return NormalizingRetriever(lexical, vocab)
    embedder = _shared_embedder()
    if embedder is None:
        return NormalizingRetriever(lexical, vocab)
    from evals.vector_cache import corpus_fingerprint, load_vectors, save_vectors
    model = getattr(embedder, "model_name", "unknown")
    cache_path = Path(corpus_dir) / "vectors.json"
    refs = [c.ref for c in chunks]
    # Keyed on the corpus's CONTENT, not just its refs: a refresh at the same
    # commit keeps every ref and rewrites the text, so refs alone would reuse
    # embeddings of text that no longer exists (see corpus_fingerprint).
    fingerprint = corpus_fingerprint(chunks)
    cached = load_vectors(cache_path, model, refs, fingerprint)
    if cached is not None:
        semantic = SemanticRetriever(chunks, embedder, vectors=cached)
    else:
        semantic = SemanticRetriever(  # embeds every chunk now
            chunks, embedder,
            timeout=_embed_timeout(len(chunks)),
            on_progress=_progress_reporter(on_progress),
        )
        save_vectors(cache_path, model, semantic.vectors, fingerprint)
    # semantic_weight=20 (lexical stays 1): measured live 2026-07-17 (T7,
    # docs/plans/2026-07-17-ast-chunking-all-languages.md) -- once AST
    # chunking fixed the embedder's 512-token truncation bug, plain 1:1 RRF
    # fusion scored WORSE (69.2% recall@5 on the comprehension board) than
    # semantic retrieval alone (84.6%), because RRF structurally rewards
    # consensus over a single retriever's excellent rank. Sweeping
    # semantic_weight found a clean plateau recovering semantic-alone's
    # ceiling starting at weight=15 and holding flat through 100; 20 sits
    # inside that plateau with margin. See evals/retriever.py's
    # HybridRetriever docstring for the full measurement.
    hybrid = HybridRetriever(lexical, semantic, semantic_weight=20.0, lexical_weight=1.0)
    return NormalizingRetriever(hybrid, vocab)


def _build_gated_pipeline(corpus_dir, fast=False, on_progress=None):
    """Build the one trust-checked writer pipeline; `fast` changes retrieval only."""
    from evals.trust import assert_safe_for_private
    from evals.ingest import fetch_ref_detail, fetch_commit_detail
    provider = make_provider("gemini-paid")
    assert_safe_for_private(provider)
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    meta = load_meta(Path(corpus_dir) / "meta.json") or {}
    repo = meta.get("repo")
    # Live exact-ref fetch: an explicit "PR/issue #N" outside the pre-indexed
    # slice (fetch_prs/fetch_issues cap at the most-recent PR_LIMIT/ISSUE_LIMIT)
    # is fetched on demand with its discussion, instead of a useless abstention
    # on an old ref. Same treatment for an explicit commit SHA, never indexed.
    #
    # The token arrives PER CALL (`answer(question, token=...)`), not at build
    # time, and is never stored on the Library or the pipeline -- so it lives
    # only for the duration of the request that supplied it, matching the
    # ingest path's own rule. Until 2026-07-28 this was hardcoded token=None,
    # which meant a PRIVATE repo's live fetch always failed safe to None: the
    # Company Brain silently had no exact-ref depth at all. Absent a token it
    # still fails safe to None -- an abstention, never an exposure.
    live = (lambda num, tok=None: fetch_ref_detail(repo, num, token=tok)) if repo else None
    live_commit = (lambda sha, tok=None: fetch_commit_detail(repo, sha, token=tok)) if repo else None
    return GatedPipeline(_build_retriever(chunks, corpus_dir, fast=fast, on_progress=on_progress),
                         chunks, provider,
                         live_fetch=live, live_commit_fetch=live_commit)


def _slug(repo):
    return repo.replace("/", "__")


class Library:
    def __init__(self, default_corpus_dir, cache_root, default_repo,
                 build_pipeline=_build_gated_pipeline, ingest_fn=ingest_repo,
                 private_root=None, private_ingest_fn=None,
                 clock=time.monotonic):
        self._default_dir = Path(default_corpus_dir)
        self._cache_root = Path(cache_root)  # SHARED public-repo cache (deduped across users)
        # PER-USER private-repo storage -- never shared, never pooled. A private
        # repo's corpus lives here, under the caller's own identity dir, and is
        # deleted on disconnect. None disables private repos for this Library.
        self._private_root = Path(private_root) if private_root else None
        self._default_repo = default_repo
        self._build_pipeline = build_pipeline
        self._ingest_fn = ingest_fn
        # Private ingest is a DISTINCT path from the shared public ingest: it
        # writes to the per-user private root and is threaded the caller's own
        # token. Falls back to the public ingest_fn only for tests that don't
        # exercise the private path.
        self._private_ingest_fn = private_ingest_fn or ingest_fn
        self._private = False  # is the CURRENTLY connected repo private?
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
        # True when a size cap truncated the code walk -> the corpus is PARTIAL,
        # so /status can tell the user some files aren't covered (never silent).
        self._truncated = bool(meta.get("truncated", False))
        # True ONLY between stage 1 (lexical published) and stage 2 (semantic
        # installed): the window where search is real but measurably worse.
        #
        # This is an HONESTY flag, not a progress spinner. During the window an
        # abstention means "I have not finished reading", which is a different
        # claim from "no one wrote this down" -- and conflating them is exactly
        # what this product exists not to do. Proven live 2026-07-28: the same
        # question abstained 3/3 mid-window and answered 3/3 once the embed
        # finished, same corpus, same anchor, same writer.
        #
        # `phase` cannot carry this: the semantic upgrade clears phase on
        # FAILURE too, and then lexical-only is the steady state rather than a
        # window that will close.
        self._indexing = False
        # How far the semantic embed has got, and roughly how much longer --
        # None until there is something real to report. A connect takes
        # minutes (measured 185s-987s on real repos) and "Building smart
        # search…" alone cannot be told apart from a hang.
        self._progress = None
        self._clock = clock
        self._pipeline = self._build_pipeline(self._default_dir)
        self._status = "ready"

    def _resolve(self, repo, private=False):
        """-> (corpus_dir, needs_ingest). A private repo resolves to the PER-USER
        private root (isolated, never the shared public cache).

        Pure filesystem fact ONLY -- "does a corpus already exist here" --
        deliberately NOT "is it fresh enough". `registry.py`'s eviction-replay
        path calls this WITHOUT a token to decide whether an automatic resume
        is a safe cache hit; it can never re-ingest a private repo (no token
        available in that context), so answering anything other than pure
        availability here would make a chunking-scheme change silently
        downgrade a resumed private-repo user to the public default -- exactly
        what that path's own contract forbids. The T6 staleness check (does
        this corpus need a refresh because ICARUS_AST_CHUNKING changed) lives
        in `connect_sync` instead, the one caller that actually has the
        context (and, for a private repo, the token) to act on it."""
        if repo == self._default_repo:
            return self._default_dir, False
        base = self._private_root if private else self._cache_root
        cache = base / _slug(repo)
        return cache, not (cache / "chunks.jsonl").exists()

    @staticmethod
    def _corpus_is_stale(cache_dir):
        """T6 of docs/plans/2026-07-17-ast-chunking-all-languages.md: true
        when a corpus already on disk was produced by ingest logic that has
        since changed. Otherwise flipping ICARUS_AST_CHUNKING would silently do
        nothing for any already-connected repo -- `chunks.jsonl` and its
        `vectors.json` cache stay mutually consistent with EACH OTHER
        regardless (vector_cache's own ref-coverage check already self-heals
        once chunks.jsonl is regenerated -- see vector_cache.load_vectors),
        but neither one ever picks up a chunking-logic change on its own.

        Two independent triggers, because `chunking` records the CODE chunker
        only: a corpus written before PR/issue chunks carried the discussion
        (2026-07-28) has an IDENTICAL `chunking` value, so without the format
        version that fix would have deployed live and been invisible to every
        already-connected repo -- shipped and silently inert."""
        from evals.ingest import (
            CHUNKING_SCHEME_AST,
            CHUNKING_SCHEME_LINE_WINDOW,
            ast_chunking_enabled,
        )
        from evals.corpus_meta import CORPUS_FORMAT_VERSION, corpus_version
        meta = load_meta(cache_dir / "meta.json")
        if meta is None:
            # chunks.jsonl with no meta.json is an unexpected, ambiguous
            # state (the two are always written together) -- serve what's
            # there rather than force a possibly-slow re-ingest on a hunch.
            return False
        if corpus_version(meta) < CORPUS_FORMAT_VERSION:
            return True
        current = CHUNKING_SCHEME_AST if ast_chunking_enabled() else CHUNKING_SCHEME_LINE_WINDOW
        # A corpus from before this field existed has no "chunking" key at
        # all -- it was necessarily chunk_text, since ast_chunk/ts_chunk
        # didn't exist yet.
        stored = meta.get("chunking", CHUNKING_SCHEME_LINE_WINDOW)
        return stored != current

    def connect_sync(self, repo, token=None, private=False, background_upgrade=False,
                     refresh=False):
        """Ingest/cache a repo, publish lexical search, then upgrade to semantic.

        `refresh=True` forces a re-ingest of a repo that is already cached.
        Without it, a connected repo's index is frozen at the commit it was
        FIRST ingested: `_resolve` only asks whether a corpus exists, and the
        staleness check below fires only when the corpus FORMAT or chunking
        scheme changes -- never when the repository itself does. Found live,
        this repo's own index sat nine commits behind HEAD with no way to
        update it. The committed default corpus is exempt: it is the frozen,
        reproducible eval board, and re-ingesting it over the network would
        silently change what every test measures.

        `private=True` routes the corpus to this user's own private storage and
        ingests with `token` (the caller's GitHub token) so a private clone can
        authenticate. `token` is a LOCAL VARIABLE ONLY -- never stored on self,
        never logged, never in any status output.

        Stage-2 failure leaves lexical search usable and a stale upgrade cannot
        replace a newer connection. Background upgrade requires a warm replica."""
        repo = (repo or "").strip()
        if private and self._private_root is None:
            with self._lock:
                self._status, self._error = "error", "Private repos aren't enabled on this brain."
                self._phase = None
            return self.status_snapshot()
        corpus_dir, needs_ingest = self._resolve(repo, private)
        # T6 staleness check: only when we actually have the means to act on
        # it, and never for the committed default repo -- that corpus is the
        # frozen, reproducible board the eval suite depends on, never
        # silently re-ingested over the network regardless of this flag (the
        # same exemption _resolve already gives it unconditionally). A
        # private repo can't be re-ingested without the caller's token (the
        # eviction-replay resume path in registry.py calls connect_sync with
        # token=None on purpose, for an existing private corpus it can't
        # re-authenticate) -- in that case, serve the existing corpus as-is
        # rather than force a re-ingest attempt that would fail. A public
        # repo never needs a token, so its staleness always applies.
        # A REFRESH (the corpus exists but its format is out of date) is not the
        # same as a cache MISS, and the difference is load-bearing: the shared
        # ingest_fn skips its work whenever a corpus is already on disk, so a
        # refresh that doesn't say it is one gets silently swallowed and the
        # stale corpus is served forever (found live 2026-07-28, after the
        # discussion-ingest fix deployed and every already-connected repo kept
        # answering from title+body).
        # An explicit caller refresh and an automatic staleness refresh are the
        # same mechanism downstream -- both must skip the cache fast paths --
        # so they collapse into one flag here.
        refresh = bool(refresh) and repo != self._default_repo
        if (repo != self._default_repo and not needs_ingest and not refresh
                and not (private and token is None)):
            refresh = self._corpus_is_stale(corpus_dir)
        needs_ingest = needs_ingest or refresh
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
                # PRIVATE repos take a distinct, per-user, token-authenticated
                # ingest; PUBLIC repos take the shared, tokenless one.
                if private:
                    self._private_ingest_fn(repo, corpus_dir, code_dir=".", token=token,
                                            refresh=refresh)
                else:
                    self._ingest_fn(repo, corpus_dir, code_dir=".", refresh=refresh)
            meta = load_meta(Path(corpus_dir) / "meta.json") or {}
            connected_repo = meta.get("repo", repo)

            # STAGE 1 -- fast, lexical-only; publishes "ready" immediately.
            fast_pipeline = self._build_pipeline(corpus_dir, fast=True)
            with self._lock:
                self._pipeline = fast_pipeline
                self._repo = connected_repo
                self._commit = meta.get("commit", "")
                self._counts = meta.get("counts")
                self._truncated = bool(meta.get("truncated", False))
                self._private = private
                self._status, self._error = "ready", None
                # Ready to search NOW (lexical); stage 2 upgrades to semantic in
                # the background. The phase says so honestly -- the repo is
                # usable, and getting smarter -- until _upgrade_to_semantic clears it.
                self._phase = "Building smart search…"
                self._indexing = True
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
            # The USER message stays generic (command lines and URLs must never
            # reach it), but the SERVER log has to be diagnosable. Logging only
            # the exception TYPE meant a real connect failure read as
            # "CalledProcessError" and nothing else -- which cost a live
            # debugging session on 2026-07-28, since the actual cause was a
            # specific gh command's stderr that was captured and discarded.
            detail = ""
            cmd = getattr(e, "cmd", None)
            if cmd:
                detail += f" cmd={' '.join(str(c) for c in cmd)[:200]!r}"
            err = getattr(e, "stderr", None)
            if err:
                detail += f" stderr={str(err)[:300]!r}"
            print(f"connect failed for {repo!r} ({type(e).__name__}){detail}",
                  file=sys.stderr)
            with self._lock:
                self._status = "error"
                self._phase = None
                self._error = "Couldn't index that repo. Check it's a public owner/name and try again."
        finally:
            # Backstop for failure before stage 1 released the slot.
            with self._lock:
                self._inflight.discard(repo)
        return self.status_snapshot()

    def _embed_progress(self, generation, started):
        """Record embed progress for `/status`, ignoring a SUPERSEDED connect.

        Same generation guard the pipeline swap uses: a stale embed finishing
        its loop must not rewind the progress a newer connect is reporting.

        The ETA is measured from THIS run's own rate rather than a constant --
        embedding speed varies with chunk length and with how busy the host
        is, so a hardcoded seconds-per-chunk would be confidently wrong. It
        stays None until at least one chunk has been embedded: there is no
        honest estimate before there is a rate."""
        def report(done, total):
            with self._lock:
                if self._generation != generation:
                    return
                if done >= total:
                    self._progress = None   # finished; nothing left to wait for
                    return
                elapsed = self._clock() - started
                eta = int((elapsed / done) * (total - done)) if done > 0 and elapsed > 0 else None
                self._progress = {"done": done, "total": total, "eta_seconds": eta}
        return report

    def _upgrade_to_semantic(self, corpus_dir, connected_repo, generation):
        """Install semantic search if this is still the newest connection."""
        try:
            full_pipeline = self._build_pipeline(
                corpus_dir, on_progress=self._embed_progress(generation, self._clock()))
            with self._lock:
                if self._generation == generation:  # still the latest connect
                    self._pipeline = full_pipeline
                    self._phase = None  # smart search ready; nothing pending
                    self._indexing = False
                    self._progress = None
        except Exception as e:
            print(
                f"semantic upgrade failed for {connected_repo!r} "
                f"({type(e).__name__}); staying on lexical-only search",
                file=sys.stderr,
            )
            with self._lock:
                if self._generation == generation:
                    self._phase = None  # gave up on the upgrade; lexical stays, nothing pending
                    self._progress = None
                    # Cleared on failure too: lexical-only is now the STEADY
                    # state, not a window about to close, and telling a user
                    # "still indexing" forever would be its own false claim.
                    # The degradation is real and logged above; surfacing a
                    # permanent one needs an error path, not this flag.
                    self._indexing = False

    def current_pipeline(self):
        with self._lock:
            return self._pipeline

    def provenance(self):
        with self._lock:
            return self._repo, self._commit

    def status_snapshot(self):
        with self._lock:
            return {"state": self._status, "repo": self._repo, "commit": self._commit,
                    "counts": self._counts, "error": self._error, "phase": self._phase,
                    "private": self._private, "truncated": self._truncated,
                    "indexing": self._indexing,
                    "indexing_progress": self._progress}
