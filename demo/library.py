# demo/library.py
"""The demo's active-repo state: which corpus is loaded, its pipeline, and the
status of switching to another repo.

One active repo at a time. The built-in `simonw/llm` uses the committed corpus;
any other public repo is ingested once into a git-ignored cache and reused after.
A lock guards the swap so /ask always sees a consistent pipeline; during a slow
ingest the previous repo stays answerable (status just reads "indexing").
"""

import threading
from pathlib import Path

from evals.corpus import load_chunks
from evals.corpus_meta import load_meta
from evals.retriever import LexicalRetriever
from evals.provider import make_provider, has_provider_key
from evals.pipeline import GatedPipeline
from evals.ingest import ingest_repo


def _pick_writer():
    return "groq" if has_provider_key("groq") else "gemini" if has_provider_key("gemini") else "openrouter"


def _default_build_pipeline(corpus_dir):
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(LexicalRetriever(chunks), chunks, make_provider(_pick_writer()))


def _default_build_private_pipeline(corpus_dir):
    # The interlock is checked at construction -- the single chokepoint where
    # the provider is fixed for this pipeline's lifetime.
    from evals.trust import assert_safe_for_private
    provider = make_provider("gemini-paid")
    assert_safe_for_private(provider)
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


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

    def connect_sync(self, repo, token=None, private=False):
        """Switch the active repo (blocking). Ingests on a cache miss. On failure
        the previous repo stays active; status becomes 'error'.

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
            pipeline = build_pipeline(corpus_dir)
            meta = load_meta(Path(corpus_dir) / "meta.json") or {}
            with self._lock:
                self._pipeline = pipeline
                self._repo = meta.get("repo", repo)
                self._commit = meta.get("commit", "")
                self._counts = meta.get("counts")
                self._private = private
                self._status, self._error = "ready", None
        except Exception:  # keep the previous repo answerable; never leak internals
            with self._lock:
                self._status = "error"
                self._error = "Couldn't index that repo. Check it's a public owner/name and try again."
        finally:
            with self._lock:
                self._inflight.discard(repo)
        return self.status_snapshot()

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
