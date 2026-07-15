# demo/registry.py
"""Per-user library isolation: one Library per authenticated GitHub identity.

**What is per-user vs. shared.** Isolation is keyed on PROVENANCE, not on user:

- A PUBLIC repo's index is a deterministic function of public input -- the same
  bytes for every user, containing zero user data -- so it is ingested ONCE into
  a shared `<storage_root>/public.cache/<repo>/` and reused by everyone. Giving
  each user a private copy of identical public data isn't privacy, it's waste
  (30 testers connecting the same repo would mean 30 identical clones + embeds).
  This is the same read-only-sharing the default demo corpus already used.
- WHO connected WHAT, their history, and their questions stay per-user: each
  user gets their own `Library` (active repo, in-memory state) and their own
  `<storage_root>/<user_id>/` record dir. (Private/customer repos, if ever
  re-enabled, must ingest into a per-user dir -- NEVER the shared path.)

Live libraries are LRU-bounded. The registry remembers each user's last repo
outside the evictable `Library` objects and replays its disk-cache hit when the
library is rebuilt, so eviction never silently reverts a user to the demo repo.

`disconnect` forgets the user's connection and deletes their own record dir --
never the shared public cache, which is nobody's private data.

Concurrency: the shared cache is written atomically (ingest into a temp dir,
then `os.replace` into place), and a per-repo lock single-flights concurrent
first-connects within a process. Because the corpus is deterministic, a race
ACROSS processes (multiple replicas on one shared volume) is harmless -- the
loser of the atomic rename discards its identical copy."""

import os
import re
import shutil
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

from .library import Library, _default_build_pipeline
from evals.ingest import ingest_repo

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ANON = "anon"  # unauthenticated GETs share one read-only default view
# Shared public-corpus root under storage_root. The '.' is deliberate: it can
# never be produced by `_key` (whose whitelist forbids '.'), so no user id can
# ever collide with or reach into the shared cache.
_PUBLIC_CACHE_SUBDIR = "public.cache"


class LibraryRegistry:
    def __init__(self, default_corpus_dir, storage_root, default_repo,
                 build_pipeline=None, ingest_fn=None, max_live=32):
        self._default_dir = Path(default_corpus_dir)
        self._storage_root = Path(storage_root)
        self._default_repo = default_repo
        self._base_build = build_pipeline or _default_build_pipeline
        self._ingest_fn = ingest_fn or ingest_repo
        self._max_live = max_live
        # One shared cache for every public repo (see module docstring).
        self._public_cache = self._storage_root / _PUBLIC_CACHE_SUBDIR
        # Built once, shared read-only across every user (see module docstring).
        self._default_pipeline = self._base_build(self._default_dir)
        self._libraries: OrderedDict[str, Library] = OrderedDict()
        self._last_repo: dict[str, str] = {}  # key -> most-recently-connected repo
        self._last_private: dict[str, bool] = {}  # key -> was that repo private?
        self._ingest_locks: dict[str, threading.Lock] = {}  # repo slug -> single-flight lock
        self._lock = threading.Lock()

    def _build(self, corpus_dir, fast=False):
        if Path(corpus_dir).resolve() == self._default_dir.resolve():
            return self._default_pipeline
        return self._base_build(corpus_dir, fast=fast)

    def _lock_for_slug(self, slug):
        with self._lock:
            lock = self._ingest_locks.get(slug)
            if lock is None:
                lock = self._ingest_locks[slug] = threading.Lock()
            return lock

    def _shared_ingest(self, repo, out_dir, code_dir=".", commit=None, token=None):
        """Ingest a public repo into the SHARED cache, once, atomically.

        `out_dir` is the final shared slug dir (Library resolves it against the
        shared cache root). Fast path: if it already holds a corpus, do nothing --
        a cache hit shared across all users. Otherwise single-flight on a per-slug
        lock, ingest into a temp dir, and `os.replace` it into place so a crashed
        or concurrent ingest can never leave a partial corpus visible to anyone.
        A cross-replica loser of the rename discards its (identical) copy."""
        out_dir = Path(out_dir)
        slug = out_dir.name
        if (out_dir / "chunks.jsonl").exists():
            return  # already cached by someone -- no lock, no work
        with self._lock_for_slug(slug):
            if (out_dir / "chunks.jsonl").exists():
                return  # another caller finished while we waited on the lock
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(tempfile.mkdtemp(prefix=f".tmp-{slug}-", dir=out_dir.parent))
            try:
                self._ingest_fn(repo, tmp, code_dir=code_dir, commit=commit, token=token)
                try:
                    os.replace(tmp, out_dir)  # atomic publish (temp and final share a parent)
                except OSError:
                    # Another process/replica published first onto the shared
                    # volume. The corpus is deterministic, so theirs == ours;
                    # keep theirs, drop ours. Re-raise only if nothing landed.
                    if (out_dir / "chunks.jsonl").exists():
                        shutil.rmtree(tmp, ignore_errors=True)
                    else:
                        raise
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise

    def _private_ingest(self, repo, out_dir, code_dir=".", commit=None, token=None):
        """Ingest a PRIVATE repo into the caller's own per-user storage, with the
        caller's own token. Deliberately NOT `_shared_ingest`: private code is
        per-tenant and must NEVER touch the shared public cache or be pooled
        across users. No cross-user lock is needed -- each user has their own
        Library and their own private_root -- but the publish is still atomic
        (temp dir + os.replace) so a crashed ingest can't leave a partial corpus.
        `token` is used only to authenticate the clone and is never stored."""
        out_dir = Path(out_dir)
        if (out_dir / "chunks.jsonl").exists():
            return  # already cached in this user's private storage
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".tmp-priv-", dir=out_dir.parent))
        try:
            self._ingest_fn(repo, tmp, code_dir=code_dir, commit=commit, token=token)
            os.replace(tmp, out_dir)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise

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
            # PUBLIC corpora live in the SHARED cache (deduped across users);
            # PRIVATE corpora live in this user's OWN <storage>/<key>/private
            # (never shared, never pooled) and ingest with the caller's token.
            lib = Library(self._default_dir, self._public_cache,
                          self._default_repo, build_pipeline=self._build,
                          ingest_fn=self._shared_ingest,
                          private_root=self._storage_root / key / "private",
                          private_ingest_fn=self._private_ingest)
            self._libraries[key] = lib
            self._libraries.move_to_end(key)
            if len(self._libraries) > self._max_live:
                evicted_key, evicted = self._libraries.popitem(last=False)
                # Record the repo (and whether it was private) while still holding
                # the registry lock so a racing rebuild can't start on the demo repo.
                snap = evicted.status_snapshot()
                self._last_repo[evicted_key] = snap["repo"]
                self._last_private[evicted_key] = snap["private"]
        # Replay the user's last connect on a freshly (re)built Library so an
        # eviction never silently reverts them to the public demo repo. This is a
        # cache hit -- connect_sync sees the on-disk cache and skips ingest.
        if resume_repo and resume_repo != self._default_repo:
            if resume_private:
                # No token to replay a private connect with (tokens are per-request,
                # never stored). Resume ONLY if the private corpus is still on disk
                # (a genuine cache hit, which connect_sync never touches token for);
                # otherwise leave the user on the default and let the next explicit
                # /connect (which carries their token) reestablish it. NEVER silently
                # downgrade a private repo to a public/wrong connection.
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
        try:
            shutil.rmtree(target)
        except FileNotFoundError:
            pass  # already deleted is successful; every other failure surfaces
