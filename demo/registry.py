# demo/registry.py
"""Per-user library isolation: one Library per authenticated GitHub identity.

This is the load-bearing isolation the unified-cloud decision demands: every
user's active repo, corpus cache, and pipeline live under their own
<storage_root>/<user_id>/ and are invisible to everyone else. The shared
default corpus (the committed public demo repo) is built once and shared
read-only. Live libraries are LRU-bounded; an evicted one rebuilds from its
disk cache on the next request. `disconnect` deletes a user's storage —
a trust product must let a user delete."""

import re
import shutil
import threading
from collections import OrderedDict
from pathlib import Path

from .library import Library, _default_build_pipeline
from evals.ingest import ingest_repo

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ANON = "anon"  # unauthenticated GETs share one read-only default view


class LibraryRegistry:
    def __init__(self, default_corpus_dir, storage_root, default_repo,
                 build_pipeline=None, ingest_fn=None, max_live=32):
        self._default_dir = Path(default_corpus_dir)
        self._storage_root = Path(storage_root)
        self._default_repo = default_repo
        self._base_build = build_pipeline or _default_build_pipeline
        self._ingest_fn = ingest_fn or ingest_repo
        self._max_live = max_live
        # Built once, shared read-only: GatedPipeline holds no per-request state.
        self._default_pipeline = self._base_build(self._default_dir)
        self._libraries: OrderedDict[str, Library] = OrderedDict()
        self._lock = threading.Lock()

    def _build(self, corpus_dir):
        if Path(corpus_dir).resolve() == self._default_dir.resolve():
            return self._default_pipeline
        return self._base_build(corpus_dir)

    @staticmethod
    def _key(user_id):
        key = user_id if user_id is not None else _ANON
        if not _SAFE_ID.match(key or ""):
            raise ValueError("invalid user id")  # ids come from GitHub; belt+braces
        return key

    def library_for(self, user_id) -> Library:
        key = self._key(user_id)
        with self._lock:
            lib = self._libraries.get(key)
            if lib is None:
                lib = Library(self._default_dir, self._storage_root / key / "cache",
                              self._default_repo, build_pipeline=self._build,
                              ingest_fn=self._ingest_fn)
                self._libraries[key] = lib
            self._libraries.move_to_end(key)
            while len(self._libraries) > self._max_live:
                self._libraries.popitem(last=False)
            return lib

    def disconnect(self, user_id):
        """Forget the user's library and delete their storage from disk."""
        key = self._key(user_id)
        with self._lock:
            self._libraries.pop(key, None)
        target = (self._storage_root / key).resolve()
        root = self._storage_root.resolve()
        if root != target and root not in target.parents:
            raise ValueError("unsafe path")  # never delete outside storage_root
        shutil.rmtree(target, ignore_errors=True)
