# demo/registry.py
"""Per-user library isolation: one Library per authenticated GitHub identity.

This is the load-bearing isolation the unified-cloud decision demands: every
user's active repo, corpus cache, and pipeline live under their own
<storage_root>/<user_id>/ and are invisible to everyone else. The shared
default corpus (the committed public demo repo) is built once and shared
read-only (see `evals/pipeline.py`'s `GatedPipeline.answer()` -- it takes the
question in, returns a `Result`, and keeps no per-call state, so one instance
is safe to hand to every user).

Live libraries are LRU-bounded. `Library.__init__` (demo/library.py) only ever
starts a fresh instance on `default_repo`'s state -- it has no way to notice
that its own `cache_root` already holds a different repo's cache from a prior
connect, so a naive rebuild-on-demand would silently and invisibly revert an
evicted user back to the public demo repo. To keep that continuity, the
registry remembers each user's last-connected repo itself (outside the
LRU-evictable `Library` objects) and, on rebuild, replays `connect_sync` on
the fresh instance -- which is a cache hit against the user's own on-disk
corpus (no re-ingest), so it just re-hydrates in-memory state from disk.

`disconnect` deletes a user's storage -- a trust product must let a user
delete -- and forgets their last-connected repo too."""

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
        # Built once, shared read-only across every user (see module docstring).
        self._default_pipeline = self._base_build(self._default_dir)
        self._libraries: OrderedDict[str, Library] = OrderedDict()
        self._last_repo: dict[str, str] = {}  # key -> most-recently-connected repo
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
            if lib is not None:
                self._libraries.move_to_end(key)
                return lib
            resume_repo = self._last_repo.get(key)
            evicted = None
            lib = Library(self._default_dir, self._storage_root / key / "cache",
                          self._default_repo, build_pipeline=self._build,
                          ingest_fn=self._ingest_fn)
            self._libraries[key] = lib
            self._libraries.move_to_end(key)
            if len(self._libraries) > self._max_live:
                evicted_key, evicted = self._libraries.popitem(last=False)
        # Remember the outgoing library's repo for its own future rebuild --
        # done outside the lock since status_snapshot() takes Library's lock.
        if evicted is not None:
            self._last_repo[evicted_key] = evicted.status_snapshot()["repo"]
        # Replay the user's last connect on a freshly (re)built Library so an
        # eviction never silently reverts them to the public demo repo. This
        # is a cache hit -- connect_sync sees the on-disk cache and skips
        # ingest -- so it only re-hydrates in-memory state, it doesn't refetch.
        if resume_repo and resume_repo != self._default_repo:
            lib.connect_sync(resume_repo)
        return lib

    def disconnect(self, user_id):
        """Forget the user's library and last-connected repo, and delete their
        storage from disk."""
        key = self._key(user_id)
        with self._lock:
            self._libraries.pop(key, None)
            self._last_repo.pop(key, None)
        target = (self._storage_root / key).resolve()
        root = self._storage_root.resolve()
        # Traversal is already fully closed by `_key`'s whitelist regex above --
        # no key can ever produce a `target` outside `storage_root`. This check
        # is symlink defense-in-depth (e.g. `storage_root` itself resolving
        # somewhere unexpected), not the primary guard.
        if root != target and root not in target.parents:
            raise ValueError("unsafe path")  # never delete outside storage_root
        shutil.rmtree(target, ignore_errors=True)
