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

    def _resolve(self, repo):
        """-> (corpus_dir, needs_ingest)."""
        if repo == self._default_repo:
            return self._default_dir, False
        cache = self._cache_dir(repo)
        return cache, not (cache / "chunks.jsonl").exists()

    def connect_sync(self, repo):
        """Switch the active repo (blocking). Ingests on a cache miss. On failure
        the previous repo stays active; status becomes 'error'."""
        repo = (repo or "").strip()
        corpus_dir, needs_ingest = self._resolve(repo)
        try:
            if needs_ingest:
                with self._lock:
                    self._status, self._error = "indexing", None
                self._ingest_fn(repo, corpus_dir)
            pipeline = self._build_pipeline(corpus_dir)
            meta = load_meta(Path(corpus_dir) / "meta.json") or {}
            with self._lock:
                self._pipeline = pipeline
                self._repo = meta.get("repo", repo)
                self._commit = meta.get("commit", "")
                self._counts = meta.get("counts")
                self._status, self._error = "ready", None
        except Exception as e:  # keep the previous repo answerable
            with self._lock:
                self._status, self._error = "error", str(e)
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
                    "counts": self._counts, "error": self._error}
