# demo/registry.py
"""Per-user library isolation: one Library per authenticated GitHub identity.

**What is per-user vs. shared.** Isolation is keyed on PROVENANCE, not on user:

- A PUBLIC repo's index is a deterministic function of public input -- the same
  bytes for every user, containing zero user data -- so it is ingested ONCE into
  a shared `<storage_root>/public.cache/<repo>/` and reused by everyone. Giving
  each user a private copy of identical public data isn't privacy, it's waste
  (30 testers connecting the same repo would mean 30 identical clones + embeds).
  This is the same read-only-sharing the default demo corpus already used.
- A PRIVATE repo's index is ALSO ingested once, into its own shared
  `<storage_root>/private.cache/<repo>/`, and read by everyone GitHub says may
  read that repo (T1, 2026-07-27). Shared-between-entitled-readers is NOT the
  same as public, hence a separate root that no unauthenticated path serves.
  **What isolates private corpora is no longer the storage layout** -- it is the
  read-side entitlement check in `demo/server.py` (`_entitled`, backed by
  `demo/auth.RepoAccessVerifier`), which asks GitHub on every read. Before that
  guard existed, per-user directories were the only thing separating tenants;
  duplicating a corpus per person is now pure waste, and it is what stopped
  colleagues at one company from sharing a brain.
- WHO connected WHAT stays per-user: each user gets their own `Library` (active
  repo, in-memory state) and their own `<storage_root>/<user_id>/` record dir,
  so one person exploring a public repo never moves anyone else's view.

Live libraries are LRU-bounded. The registry remembers each user's last repo
outside the evictable `Library` objects and replays its disk-cache hit when the
library is rebuilt, so eviction never silently reverts a user to the demo repo.

`disconnect` forgets the user's connection and deletes their own record dir --
never a shared corpus, public or private. Under shared storage the old
"disconnect deletes the corpus" behaviour would let one person destroy their
whole team's brain while tidying up their own account (D4, 2026-07-27). It also
means an engineer can point Icarus at any public repo to try something out and
disconnect again without touching their company's index.

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

from .library import Library, _build_gated_pipeline
from evals.ingest import ingest_repo

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ANON = "anon"  # unauthenticated GETs share one read-only default view
# Shared public-corpus root under storage_root. The '.' is deliberate: it can
# never be produced by `_key` (whose whitelist forbids '.'), so no user id can
# ever collide with or reach into the shared cache.
_PUBLIC_CACHE_SUBDIR = "public.cache"
# Shared PRIVATE-corpus root. Shared between everyone GitHub says may read that
# repo -- which is not the same as public, and it is deliberately a separate root
# so no unauthenticated/public path can ever serve out of it. Same '.' trick as
# above: `_key`'s whitelist forbids '.', so no user id can collide with or reach
# into either cache.
_PRIVATE_CACHE_SUBDIR = "private.cache"


class LibraryRegistry:
    def __init__(self, default_corpus_dir, storage_root, default_repo,
                 build_pipeline=None, ingest_fn=None, max_live=32):
        self._default_dir = Path(default_corpus_dir)
        self._storage_root = Path(storage_root)
        self._default_repo = default_repo
        self._base_build = build_pipeline or _build_gated_pipeline
        self._ingest_fn = ingest_fn or ingest_repo
        self._max_live = max_live
        # One shared cache for every public repo (see module docstring).
        self._public_cache = self._storage_root / _PUBLIC_CACHE_SUBDIR
        # One shared corpus per PRIVATE repo, read by everyone entitled to it.
        self._private_cache = self._storage_root / _PRIVATE_CACHE_SUBDIR
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

    def _ingest_once(self, repo, out_dir, code_dir=".", commit=None, token=None,
                     refresh=False):
        """Ingest a repo into `out_dir`, once, atomically — public or private.

        One function for both since T1 (2026-07-27). Which root `out_dir` sits
        under is chosen by `Library` (public cache vs private cache) and that
        choice is the whole separation; the publish mechanics are identical, and
        private corpora now need the same single-flight lock public ones always
        had, because two colleagues can race to connect the same private repo.

        `out_dir` is the final shared slug dir (Library resolves it against the
        shared cache root). Fast path: if it already holds a corpus, do nothing --
        a cache hit shared across all users. Otherwise single-flight on a per-slug
        lock, ingest into a temp dir, and `os.replace` it into place so a crashed
        or concurrent ingest can never leave a partial corpus visible to anyone.
        A cross-replica loser of the rename discards its (identical) copy.

        `refresh=True` means the caller has already determined the corpus on
        disk is OUT OF DATE, so both cache-hit fast paths must be skipped. They
        cannot be left in place "because a corpus exists" -- that is exactly
        the condition a refresh describes. Without this the caller's staleness
        decision is computed and then silently discarded here, and the stale
        corpus is served forever: found live 2026-07-28, when the
        discussion-ingest fix deployed correctly and every ALREADY-connected
        repo kept answering from title+body, because `Library` asked for a
        re-ingest and this function returned without doing one."""
        out_dir = Path(out_dir)
        slug = out_dir.name
        if not refresh and (out_dir / "chunks.jsonl").exists():
            return  # already cached by someone -- no lock, no work
        with self._lock_for_slug(slug):
            if not refresh and (out_dir / "chunks.jsonl").exists():
                return  # another caller finished while we waited on the lock
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(tempfile.mkdtemp(prefix=f".tmp-{slug}-", dir=out_dir.parent))
            try:
                self._ingest_fn(repo, tmp, code_dir=code_dir, commit=commit, token=token)
                self._publish(tmp, out_dir, slug)
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise

    @staticmethod
    def _publish(tmp, out_dir, slug):
        """Move a freshly-ingested temp dir into its final shared location.

        `os.replace` publishes atomically onto a MISSING destination, which is
        the cache-fill case. It cannot replace a non-empty directory (ENOTEMPTY
        on POSIX), so a refresh swaps instead: move the current corpus aside,
        publish, then delete the old one. The gap where the destination does not
        exist is two renames wide, and a reader arriving inside it sees a cache
        miss and waits on this same per-slug lock -- a redundant wait, never a
        partial or mixed corpus."""
        try:
            os.replace(tmp, out_dir)  # atomic publish (temp and final share a parent)
            return
        except OSError:
            if not out_dir.exists():
                # Nothing landed and nothing was there -- a real failure.
                raise
        if not (out_dir / "chunks.jsonl").exists():
            # A directory exists but holds no corpus (an interrupted publish).
            # Clear it and retry rather than treating it as a live corpus.
            shutil.rmtree(out_dir, ignore_errors=True)
            os.replace(tmp, out_dir)
            return
        stale = Path(tempfile.mkdtemp(prefix=f".stale-{slug}-", dir=out_dir.parent))
        try:
            os.replace(out_dir, stale)   # empty dir as the destination: allowed
        except OSError:
            # Another process/replica published first onto the shared volume.
            # The corpus is deterministic, so theirs == ours; keep theirs.
            shutil.rmtree(stale, ignore_errors=True)
            shutil.rmtree(tmp, ignore_errors=True)
            return
        os.replace(tmp, out_dir)
        shutil.rmtree(stale, ignore_errors=True)

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
                          ingest_fn=self._ingest_once,
                          private_root=self._private_cache,
                          private_ingest_fn=self._ingest_once)
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
        """Forget the caller's library and last-connected repo, and delete their
        OWN record dir -- never a shared corpus (see module docstring, D4)."""
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
