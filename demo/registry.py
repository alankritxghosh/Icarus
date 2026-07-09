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
registry remembers each user's last-connected repo (and whether it was
private) itself (outside the LRU-evictable `Library` objects) and, on
rebuild, replays `connect_sync` on the fresh instance -- which is a cache hit
against the user's own on-disk corpus (no re-ingest), so it just re-hydrates
in-memory state from disk.

A private repo's resume is more constrained: the registry never holds the
caller's GitHub token (tokens are per-request, never stored -- see
demo/server.py), so it cannot replay a private connect that would need to
re-ingest. It resumes a private repo ONLY when that repo's corpus cache still
exists on disk (a genuine cache hit, which `connect_sync` proves never touches
`token`); otherwise it leaves the rebuilt Library on the default repo and lets
the next explicit `/connect` (which DOES carry the caller's token) reestablish
it. A private repo must NEVER silently resume reporting `private: False` --
that would mean answering from the free/public writer or the wrong storage
root for what the user believes is still their private connection.

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
                 build_pipeline=None, ingest_fn=None, max_live=32,
                 build_private_pipeline=None, private_ready=None):
        self._default_dir = Path(default_corpus_dir)
        self._storage_root = Path(storage_root)
        self._default_repo = default_repo
        self._base_build = build_pipeline or _default_build_pipeline
        self._ingest_fn = ingest_fn or ingest_repo
        self._max_live = max_live
        # Forwarded to each Library UNCHANGED -- unlike the public build_pipeline,
        # a private repo is never shared across users, so there's nothing here to
        # wrap the way self._build wraps the shared default pipeline below.
        self._build_private_pipeline = build_private_pipeline
        self._private_ready = private_ready
        # Built once, shared read-only across every user (see module docstring).
        self._default_pipeline = self._base_build(self._default_dir)
        self._libraries: OrderedDict[str, Library] = OrderedDict()
        self._last_repo: dict[str, str] = {}  # key -> most-recently-connected repo
        self._last_private: dict[str, bool] = {}  # key -> was that repo private?
        self._lock = threading.Lock()

    def _build(self, corpus_dir, fast=False):
        if Path(corpus_dir).resolve() == self._default_dir.resolve():
            return self._default_pipeline
        return self._base_build(corpus_dir, fast=fast)

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
            resume_private = self._last_private.get(key, False)
            # Only forward the private-pipeline overrides if the registry itself
            # was given them -- otherwise omit the kwargs entirely so Library's
            # own defaults (_default_build_private_pipeline/_default_private_ready)
            # apply, rather than overriding them with an explicit None.
            private_kwargs = {}
            if self._build_private_pipeline is not None:
                private_kwargs["build_private_pipeline"] = self._build_private_pipeline
            if self._private_ready is not None:
                private_kwargs["private_ready"] = self._private_ready
            lib = Library(self._default_dir, self._storage_root / key / "cache",
                          self._default_repo, build_pipeline=self._build,
                          ingest_fn=self._ingest_fn, **private_kwargs)
            self._libraries[key] = lib
            self._libraries.move_to_end(key)
            if len(self._libraries) > self._max_live:
                evicted_key, evicted = self._libraries.popitem(last=False)
                # Capture the outgoing library's repo (and whether it was
                # private) and record both while STILL holding self._lock, so
                # no other thread can ever observe the "popped from
                # _libraries but not yet in _last_repo/_last_private" gap --
                # that gap is exactly what would let the evicted user's own
                # next library_for() race in and rebuild on the default repo
                # instead of resuming. status_snapshot() only takes Library's
                # own lock (see demo/library.py) and Library holds no
                # reference back to the registry, so registry-lock ->
                # library-lock is a safe, cycle-free one-way ordering -- no
                # deadlock risk.
                snap = evicted.status_snapshot()
                self._last_repo[evicted_key] = snap["repo"]
                self._last_private[evicted_key] = snap["private"]
        # Replay the user's last connect on a freshly (re)built Library so an
        # eviction never silently reverts them to the public demo repo. This
        # is a cache hit -- connect_sync sees the on-disk cache and skips
        # ingest -- so it only re-hydrates in-memory state, it doesn't refetch.
        if resume_repo and resume_repo != self._default_repo:
            if resume_private:
                # No token to replay a private connect with (tokens are
                # per-request, never stored -- see demo/server.py). Only
                # resume if the private cache still exists on disk: that's a
                # genuine cache hit, and connect_sync's ingest branch (the
                # only place `token` is ever used) is proven skipped whenever
                # needs_ingest is False, so a token-less resume is safe THERE
                # and only there. If the cache is gone, resuming would need a
                # fresh ingest we have no token for -- fail safe by leaving
                # the rebuilt Library on the default repo (honest: the next
                # explicit /connect, which carries the caller's token, will
                # reestablish it) rather than ever silently downgrading a
                # private repo to a public connect.
                _, needs_ingest = lib._resolve(resume_repo, private=True)
                if not needs_ingest:
                    lib.connect_sync(resume_repo, private=True)
            else:
                lib.connect_sync(resume_repo)
        return lib

    def disconnect(self, user_id):
        """Forget the user's library and last-connected repo, and delete their
        storage from disk."""
        key = self._key(user_id)
        with self._lock:
            self._libraries.pop(key, None)
            self._last_repo.pop(key, None)
            self._last_private.pop(key, None)
        target = (self._storage_root / key).resolve()
        root = self._storage_root.resolve()
        # Traversal is already fully closed by `_key`'s whitelist regex above --
        # no key can ever produce a `target` outside `storage_root`. This check
        # is symlink defense-in-depth (e.g. `storage_root` itself resolving
        # somewhere unexpected), not the primary guard.
        if root != target and root not in target.parents:
            raise ValueError("unsafe path")  # never delete outside storage_root
        shutil.rmtree(target, ignore_errors=True)
