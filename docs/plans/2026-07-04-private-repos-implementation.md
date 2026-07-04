# Private Repos (Per-User Isolation + Paid Writer) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task. Red→green per task; never weaken a test or the honesty
> gates; never commit a token or private corpus. Every commit message ends with:
> `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

**Goal:** A signed-in engineer connects their **own private GitHub repo** on the
hosted brain and gets cited answers (or an honest unknown) — with per-user
isolation, caller-verified access, and private code reaching **only** a paid
no-training writer.

**Architecture:** The bearer gate learns *who* is calling (GitHub user id); a
`LibraryRegistry` gives each identity its own isolated `Library` (corpus + active
repo + pipeline) under a per-user directory; a deterministic **trust interlock**
(`evals/trust.py`) makes it impossible in code for a private corpus to reach a
non-private-safe provider; ingest authenticates with the *caller's* token, passed
leak-safe (env config, never argv/URL). The honesty gate is untouched.

**Tech stack:** Python 3 stdlib only (no new dependency — the paid Gemini API is
the same `urllib` REST call as the free one). Tests: `unittest`, offline by
default; live proofs self-skip without keys.

**Parent scoping doc:** [2026-07-04-private-repos-per-user-isolation.md](2026-07-04-private-repos-per-user-isolation.md)
— read it first for the *why* of every decision below. This doc is the *how*.

**Run tests from the repo root** (the `-t .` matters — package-relative imports):
```bash
python3 -m unittest demo.test_auth -v                 # one module
python3 -m unittest discover -t . -s demo             # full demo suite
python3 -m unittest discover -t . -s evals            # full evals suite
```

---

## My thinking — the five design points everything below hangs on

1. **Identity, not just validity.** `GitHubTokenVerifier.verify()` today returns a
   bool. Isolation needs a *key*, so it will return the caller's **stable numeric
   GitHub id** (as a string) or `None`. Fail-safe stays: any ambiguity → `None`.
   When auth is off (local dev), everyone is the single user `"local"` — this
   preserves today's single-user local behavior *exactly* while making the code
   path uniform.
2. **The registry is the isolation, the directory tree is the database.** One
   `Library` per user id, corpora under `<storage_root>/<user_id>/…`. No DB. The
   shared default (`simonw/llm`) pipeline is built **once** and shared read-only —
   `GatedPipeline` holds no per-request state, so sharing is safe, and it keeps
   32 users from loading the same corpus 32 times into 512 MB of RAM.
3. **`private_safe` is set at construction from a *dedicated* env var, never
   inferred.** Free and paid Gemini are the same API and could be the same key
   string — code cannot tell them apart. So the paid provider reads
   `GEMINI_PAID_API_KEY` and *only* that class carries `private_safe = True`.
   Putting a key in that env var is the operator's explicit attestation "this key
   is billed / no-training". The interlock (`assert_safe_for_private`) is then a
   two-line pure function — deterministic and auditable, like the honesty gate.
4. **One GitHub API call answers both safety questions.** `GET /repos/{owner}/{repo}`
   *with the caller's token*: a 200 proves the caller can read the repo (else we're
   an exfiltration tool), and the response's `"private"` field tells us which
   writer/storage path to use. Anything but a clean 200 → refuse. No user-supplied
   "is it private?" checkbox to get wrong.
5. **The token flows through memory only.** Handler → `connect_sync(repo, token,
   private)` → subprocess **env** (`GIT_CONFIG_*` for git, `GH_TOKEN` for gh).
   Never argv (visible in `ps`), never the clone URL (lands in git config), never
   disk, never logs, never a `__repr__`. Public connects don't get the token at
   all — a credential is a responsibility; don't spend it where it isn't needed.

**Task order = Brick order: A (identity) → B (registry) → C (interlock) → D
(private ingest) → E (proofs) → F (ops/docs). A+B alone are shippable (multi-user
isolation on public repos).**

---

# BRICK A — Identity

## Task 1: Verifier returns *who*, not just *whether*

**Files:**
- Modify: `demo/auth.py`
- Test: `demo/test_auth.py`

**Step 1: Rewrite the verifier tests to demand an identity.** Replace the
`StaticVerifierTests` and `GitHubVerifierTests` classes in `demo/test_auth.py`
(keep `BearerTokenTests` untouched):

```python
class StaticVerifierTests(unittest.TestCase):
    def test_maps_tokens_to_user_ids(self):
        v = StaticTokenVerifier({"tok-a": "1001", "tok-b": "1002"})
        self.assertEqual(v.verify("tok-a"), "1001")
        self.assertEqual(v.verify("tok-b"), "1002")
        self.assertIsNone(v.verify("bad"))
        self.assertIsNone(v.verify(""))

    def test_set_input_means_token_is_its_own_id(self):
        # Back-compat sugar for tests that don't care about the id value.
        v = StaticTokenVerifier({"good"})
        self.assertEqual(v.verify("good"), "good")


class GitHubVerifierTests(unittest.TestCase):
    def test_empty_token_never_calls_out(self):
        self.assertIsNone(GitHubTokenVerifier().verify(""))

    def test_cache_hit_returns_id_without_network(self):
        import time
        v = GitHubTokenVerifier()
        v._cache["cached"] = ("77", time.time() + 300)
        self.assertEqual(v.verify("cached"), "77")

    def test_valid_token_returns_the_github_user_id(self):
        import io
        from unittest import mock

        class _Resp(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch("urllib.request.urlopen",
                        return_value=_Resp(b'{"id": 583231, "login": "octocat"}')):
            self.assertEqual(GitHubTokenVerifier().verify("tok"), "583231")

    def test_network_error_fails_safe_to_none(self):
        import urllib.error
        from unittest import mock
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            self.assertIsNone(GitHubTokenVerifier().verify("anything"))

    def test_malformed_body_fails_safe_to_none(self):
        import io
        from unittest import mock

        class _Resp(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch("urllib.request.urlopen", return_value=_Resp(b"not json")):
            self.assertIsNone(GitHubTokenVerifier().verify("tok"))

    def test_expired_cache_entry_is_revalidated_not_trusted(self):
        import time
        import urllib.error
        from unittest import mock
        v = GitHubTokenVerifier()
        v._cache["stale"] = ("77", time.time() - 1)
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            self.assertIsNone(v.verify("stale"))
```

**Step 2: Run and watch them fail.**
Run: `python3 -m unittest demo.test_auth -v`
Expected: FAIL/ERROR — `verify` returns `True`/`False`, cache shape is wrong.

**Step 3: Implement.** In `demo/auth.py`: add `import json` at the top; update the
docstring (verify now proves *identity*, not just validity); replace the verifier
classes:

```python
class TokenVerifier:
    def verify(self, token: str) -> str | None:  # pragma: no cover - interface
        """Return the caller's stable user id, or None (fail safe)."""
        raise NotImplementedError


class StaticTokenVerifier(TokenVerifier):
    """Test double: maps allowed tokens to user ids. A set/list input means each
    token is its own id (for tests that don't care about the id value)."""

    def __init__(self, allowed):
        self._allowed = dict(allowed) if isinstance(allowed, dict) else {t: t for t in allowed}

    def verify(self, token: str) -> str | None:
        return self._allowed.get(token) if token else None


class GitHubTokenVerifier(TokenVerifier):
    """Resolves a token to the caller's stable numeric GitHub user id via
    GET /user. Caches token -> (id, expiry) for `ttl` seconds. Any error,
    non-200, or unparseable body => None (fail safe — never an identity we
    haven't seen GitHub assert)."""

    URL = "https://api.github.com/user"

    def __init__(self, ttl: float = 300.0, timeout: float = 10.0):
        self._ttl = ttl
        self._timeout = timeout
        self._cache: dict[str, tuple[str, float]] = {}

    def verify(self, token: str) -> str | None:
        if not token:
            return None
        now = time.time()
        entry = self._cache.get(token)
        if entry is not None and entry[1] > now:
            return entry[0]
        req = urllib.request.Request(
            self.URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "icarus/0.1",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status != 200:
                    return None
                user_id = str(json.loads(resp.read())["id"])
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            return None
        self._cache[token] = (user_id, now + self._ttl)
        return user_id
```

**Step 4: Run to green.**
Run: `python3 -m unittest demo.test_auth -v` → all PASS.
Then: `python3 -m unittest discover -t . -s demo` — `test_server.py`'s
`AuthGateTests` still pass unchanged (a valid token now returns `"good-token"` as
its own id, which is truthy where the server expects a bool — Task 2 makes the
server use it properly).

**Step 5: Commit.**
```bash
git add demo/auth.py demo/test_auth.py
git commit -m "feat(brain): bearer verifier returns the caller's GitHub identity"
```

## Task 2: The server threads identity through every request

**Files:**
- Modify: `demo/server.py` (the `_authenticated` method and its callers)
- Test: `demo/test_server.py`

**Step 1: Write the failing test.** Add to `demo/test_server.py` (note: the
existing `AuthGateTests.setUpClass` verifier changes to a dict):

```python
class IdentityTests(unittest.TestCase):
    """The handler resolves an identity per request: 'local' when auth is off,
    the verified GitHub id when auth is on."""

    def test_identity_is_local_when_auth_off(self):
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg)
        try:
            urllib.request.urlopen(fx.base + "/status").read()
        finally:
            fx.close()
        self.assertEqual(reg.seen, ["local"])

    def test_identity_is_the_github_id_when_auth_on(self):
        from .auth import StaticTokenVerifier
        lib = _StubLibrary()
        reg = _StubRegistry(lib)
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            data = json.dumps({"question": "Why the Responses API as a new class?"}).encode()
            req = urllib.request.Request(fx.base + "/ask", data=data,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer tok-a"})
            urllib.request.urlopen(req).read()
        finally:
            fx.close()
        self.assertIn("1001", reg.seen)
```

This needs the `_StubRegistry` (also used heavily in Task 4) — add it above
`_ServerFixture`:

```python
class _StubRegistry:
    """Stand-in for demo.registry.LibraryRegistry: one library for everyone,
    records which identities asked."""

    def __init__(self, lib):
        self.lib = lib
        self.seen = []
        self.disconnected = []

    def library_for(self, user_id):
        self.seen.append(user_id)
        return self.lib

    def disconnect(self, user_id):
        self.disconnected.append(user_id)
```

And make `_ServerFixture` accept either shape (so the many existing tests that
pass a bare `_StubLibrary` keep working):

```python
class _ServerFixture:
    def __init__(self, lib, **handler_kwargs):
        registry = lib if hasattr(lib, "library_for") else _StubRegistry(lib)
        ...  # rest unchanged, but pass `registry` to make_handler
```

Do the same one-line wrap in `ServerTests.setUpClass`
(`make_handler(_StubRegistry(cls.lib), str(cls.html))`).

**Step 2: Run to verify failure.**
Run: `python3 -m unittest demo.test_server.IdentityTests -v`
Expected: ERROR — `make_handler` calls `library.current_pipeline()` on a registry.

**Step 3: Implement in `demo/server.py`.** `make_handler`'s first parameter is now
a **registry** (rename it `registry`); replace `_authenticated` with `_identity`,
and resolve the library per request:

```python
        LOCAL_USER = "local"

        def _identity(self) -> str | None:
            """Who is calling? 'local' when auth is off (the single local
            operator); the verified GitHub user id when auth is on; None when
            auth is on and the token is missing/invalid (fail safe)."""
            if not require_auth:
                return self.LOCAL_USER
            token = bearer_token(self.headers)
            if not token or verifier is None:
                return None
            return verifier.verify(token)
```

Route changes (everything else stays byte-identical):
- `GET /health` and `GET /status`: `lib = registry.library_for(self._identity())`
  then use `lib` as before. (`library_for(None)` returns the shared anonymous
  default — Task 3 — so unauthenticated status polling still works, as the Mac
  app's pre-sign-in gate requires.)
- `POST /ask` and `POST /connect`: first `identity = self._identity()`; if
  `identity is None` → the existing 401 JSON. Then
  `lib = registry.library_for(identity)` and proceed as before (the `/connect`
  background thread targets `lib.connect_sync`).
- In `serve()`: nothing yet — Task 3 swaps the `Library` for a real registry.
  For now wrap: `registry = _single_user_registry(library)`? **No — keep it
  simpler:** `serve()` builds `Library` today; give `demo/server.py` a tiny
  adapter until Task 3 replaces it:

```python
class _SingleLibraryRegistry:
    """Interim: today's one shared Library behind the registry interface.
    Deleted in the next task."""

    def __init__(self, lib):
        self._lib = lib

    def library_for(self, user_id):
        return self._lib
```

**Step 4: Run the whole demo suite.**
Run: `python3 -m unittest discover -t . -s demo`
Expected: all PASS (including the untouched auth-gate, origin, body-cap tests).

**Step 5: Commit.**
```bash
git add demo/server.py demo/test_server.py
git commit -m "feat(brain): resolve a per-request identity; route through a registry seam"
```

---

# BRICK B — Per-user isolation

## Task 3: `LibraryRegistry` — one isolated Library per identity

**Files:**
- Create: `demo/registry.py`
- Test: `demo/test_registry.py` (create)

**Step 1: Write the failing tests** — `demo/test_registry.py`:

```python
# demo/test_registry.py
"""The registry is the isolation core: one Library per user id, per-user storage,
a shared read-only default pipeline, LRU-bounded memory, and safe disconnect."""

import json
import tempfile
import unittest
from pathlib import Path

from evals.corpus_meta import write_meta
from .registry import LibraryRegistry


def _seed_corpus(dir_, repo, commit="c0ffee"):
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "chunks.jsonl").write_text(json.dumps({"ref": "pr:1", "source": "pr", "text": "why"}) + "\n")
    write_meta(d / "meta.json", repo=repo, commit=commit, code_dir=".", counts={"pr": 1, "issue": 0, "code": 0})


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm", "94769b8")
        self.storage = root / "storage"
        self.builds = []

        def fake_build(corpus_dir):
            self.builds.append(str(corpus_dir))
            return f"pipeline::{corpus_dir}"

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                                   build_pipeline=fake_build, ingest_fn=fake_ingest)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_user_gets_the_same_library(self):
        self.assertIs(self.reg.library_for("1001"), self.reg.library_for("1001"))

    def test_different_users_get_different_libraries(self):
        self.assertIsNot(self.reg.library_for("1001"), self.reg.library_for("1002"))

    def test_users_get_per_user_storage_paths(self):
        a = self.reg.library_for("1001")
        a.connect_sync("octo/xrepo")
        cached = self.storage / "1001" / "cache" / "octo__xrepo" / "chunks.jsonl"
        self.assertTrue(cached.exists())
        self.assertFalse((self.storage / "1002").exists())

    def test_one_users_connect_never_touches_anothers_state(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        a.connect_sync("octo/xrepo")
        self.assertEqual(a.status_snapshot()["repo"], "octo/xrepo")
        self.assertEqual(b.status_snapshot()["repo"], "simonw/llm")

    def test_default_pipeline_is_built_once_and_shared(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        self.assertIs(a.current_pipeline(), b.current_pipeline())
        self.assertEqual(self.builds.count(f"pipeline::{self.default_dir}"), 1)

    def test_anonymous_maps_to_one_shared_default_view(self):
        self.assertIs(self.reg.library_for(None), self.reg.library_for(None))

    def test_hostile_user_id_is_rejected(self):
        for bad in ("../../etc", "a/b", "", "x" * 65):
            with self.assertRaises(ValueError):
                self.reg.library_for(bad)

    def test_lru_evicts_idle_libraries(self):
        reg = LibraryRegistry(self.default_dir, self.storage, "simonw/llm",
                              build_pipeline=lambda d: f"p::{d}",
                              ingest_fn=lambda *a, **k: None, max_live=2)
        first = reg.library_for("1")
        reg.library_for("2")
        reg.library_for("3")  # evicts "1"
        self.assertIsNot(reg.library_for("1"), first)  # rebuilt, disk cache intact

    def test_disconnect_deletes_only_that_users_storage(self):
        a, b = self.reg.library_for("1001"), self.reg.library_for("1002")
        a.connect_sync("octo/xrepo")
        b.connect_sync("octo/yrepo")
        self.reg.disconnect("1001")
        self.assertFalse((self.storage / "1001").exists())
        self.assertTrue((self.storage / "1002" / "cache" / "octo__yrepo").exists())
        # A fresh library for 1001 starts back on the default.
        self.assertEqual(self.reg.library_for("1001").status_snapshot()["repo"], "simonw/llm")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run to verify failure.**
Run: `python3 -m unittest demo.test_registry -v`
Expected: ERROR — `No module named 'demo.registry'` (well, ModuleNotFoundError).

**Step 3: Implement `demo/registry.py`:**

```python
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
        self._default_dir = Path(default_corpus_dir).resolve()
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
        if Path(corpus_dir).resolve() == self._default_dir:
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
```

Note `Library.__init__` builds its default pipeline via the injected
`build_pipeline` — our `self._build` returns the shared one, so per-user
construction costs nothing.

**Step 4: Run to green.**
Run: `python3 -m unittest demo.test_registry -v` → all PASS.
Also: `python3 -m unittest demo.test_library -v` (unchanged, must stay green).

**Step 5: Commit.**
```bash
git add demo/registry.py demo/test_registry.py
git commit -m "feat(brain): per-user LibraryRegistry — isolated storage, shared default, LRU, disconnect"
```

## Task 4: Wire the registry into `serve()` + add `POST /disconnect`

**Files:**
- Modify: `demo/server.py`
- Modify: `.gitignore`
- Test: `demo/test_server.py`

**Step 1: Failing tests** (add to `demo/test_server.py`):

```python
class DisconnectTests(unittest.TestCase):
    def test_disconnect_requires_auth_when_auth_on(self):
        from .auth import StaticTokenVerifier
        fx = _ServerFixture(_StubRegistry(_StubLibrary()), require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(fx.base + "/disconnect", {})
            self.assertEqual(cm.exception.code, 401)
            cm.exception.close()
        finally:
            fx.close()

    def test_disconnect_calls_registry_with_the_callers_identity(self):
        from .auth import StaticTokenVerifier
        reg = _StubRegistry(_StubLibrary())
        fx = _ServerFixture(reg, require_auth=True,
                            verifier=StaticTokenVerifier({"tok-a": "1001"}))
        try:
            req = urllib.request.Request(
                fx.base + "/disconnect", data=b"{}",
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer tok-a"})
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            fx.close()
        self.assertEqual(reg.disconnected, ["1001"])
```

**Step 2: Run to verify failure** — `python3 -m unittest demo.test_server.DisconnectTests -v`
→ 404s (route missing).

**Step 3: Implement.**
- In `do_POST`, after the `_authenticated`→identity block, add:

```python
            if self.path == "/disconnect":
                registry.disconnect(identity)
                self._send_json(200, registry.library_for(identity).status_snapshot())
                return
```

- In `serve()`: delete the `_SingleLibraryRegistry` adapter; build the real thing:

```python
    storage_root = Path(os.environ.get("ICARUS_STORAGE_ROOT", str(REPO_ROOT / "data")))
    registry = LibraryRegistry(CORPUS_DIR, storage_root, default_repo)
```

  (import `LibraryRegistry` from `.registry`; the old module-level `CACHE_ROOT`
  constant is now unused — remove it, but **leave** the `evals/corpus/cache/`
  line in `.gitignore` so old on-disk caches stay ignored).
- Update the module docstring's endpoint list (add `POST /disconnect`).
- `.gitignore`: add under the demo-cache comment block:

```gitignore
# Per-user corpora (public caches AND private code) — never committed
data/
```

**Step 4: Run everything.**
Run: `python3 -m unittest discover -t . -s demo` → all PASS.
Sanity: `python3 -m demo.server` boots and prints the banner (Ctrl-C).

**Step 5: Commit.**
```bash
git add demo/server.py demo/test_server.py .gitignore
git commit -m "feat(brain): serve per-user libraries from ICARUS_STORAGE_ROOT; POST /disconnect deletes my data"
```

---

# BRICK C — The private-safe writer + trust interlock

## Task 5: `private_safe` flags + `PaidGeminiProvider`

**Files:**
- Modify: `evals/provider.py`
- Test: `evals/test_provider.py`

**Step 1: Failing tests** (append to `evals/test_provider.py`):

```python
class PrivateSafeFlagTests(unittest.TestCase):
    """private_safe is a construction-time class property — the interlock's
    ground truth. Free tiers may train on inputs: never True for them."""

    def test_free_providers_are_not_private_safe(self):
        from .provider import OpenRouterProvider, GroqProvider, GeminiProvider
        for cls in (OpenRouterProvider, GroqProvider, GeminiProvider):
            self.assertFalse(cls().private_safe, cls.__name__)

    def test_static_provider_is_private_safe(self):
        from .provider import StaticProvider
        self.assertTrue(StaticProvider("x").private_safe)  # offline; nothing leaves

    def test_paid_gemini_is_private_safe_and_uses_its_own_key(self):
        import os
        from unittest import mock
        from .provider import PaidGeminiProvider
        p = PaidGeminiProvider()
        self.assertTrue(p.private_safe)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "free-key"}, clear=True):
            with self.assertRaises(RuntimeError):  # the FREE key must not satisfy it
                p.complete("hi")

    def test_make_provider_knows_gemini_paid(self):
        import os
        from unittest import mock
        from .provider import make_provider, has_provider_key, PaidGeminiProvider
        self.assertIsInstance(make_provider("gemini-paid"), PaidGeminiProvider)
        with mock.patch.dict(os.environ, {"GEMINI_PAID_API_KEY": "k"}, clear=True):
            self.assertTrue(has_provider_key("gemini-paid"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(has_provider_key("gemini-paid"))
```

**Step 2: Run to verify failure** — `python3 -m unittest evals.test_provider -v`
→ AttributeError/ImportError.

**Step 3: Implement in `evals/provider.py`:**
- `Provider` gets `private_safe: bool = False` as a class attribute with the
  comment: *"True only for providers whose data-use terms are verified
  no-training (or that never leave the machine). The trust interlock
  (evals/trust.py) is keyed off this — never set it on a free tier."*
- `StaticProvider`: `private_safe = True`.
- `GeminiProvider`: hoist the env-var name into a class attr so the paid
  subclass overrides one string, not the method:

```python
class GeminiProvider(Provider):
    KEY_ENV = "GEMINI_API_KEY"
    ...
    def complete(self, prompt: str) -> str:
        key = os.environ.get(self.KEY_ENV)
        if not key:
            raise RuntimeError(f"{self.KEY_ENV} not set")
        ...
```

- Add after `GeminiProvider`:

```python
class PaidGeminiProvider(GeminiProvider):
    """Gemini on a BILLING-ENABLED key. Google's paid-tier terms state inputs/
    outputs are not used to train — verified in writing, link in
    docs/plans/2026-07-04-private-repos-per-user-isolation.md. The dedicated
    KEY_ENV is deliberate: code cannot tell a free key string from a paid one,
    so placing a key in GEMINI_PAID_API_KEY is the operator's attestation that
    it is billed. Model default follows the free provider; the eval board picks
    upgrades (Gemini 3.x welcome — verify the exact id against the live API)."""

    KEY_ENV = "GEMINI_PAID_API_KEY"
    private_safe = True
```

- Register it: `_PROVIDERS["gemini-paid"] = PaidGeminiProvider`;
  `_KEY_ENV["gemini-paid"] = "GEMINI_PAID_API_KEY"`.
- Check `evals/run.py`: if `--writer` choices are a hardcoded list, add
  `gemini-paid`; if they come from `_PROVIDERS`, nothing to do. (Read the file —
  don't assume.)

**Step 4: Run to green** — `python3 -m unittest evals.test_provider -v`, then
`python3 -m unittest discover -t . -s evals` (nothing else may regress).

**Step 5: Commit.**
```bash
git add evals/provider.py evals/test_provider.py evals/run.py
git commit -m "feat(brain): PaidGeminiProvider on a dedicated billed key + private_safe flags"
```

## Task 6: The interlock — two lines that make bluffing-with-data impossible

**Files:**
- Create: `evals/trust.py`
- Test: `evals/test_trust.py` (create)

**Step 1: Failing test** — `evals/test_trust.py`:

```python
# evals/test_trust.py
"""The trust interlock: private code may only reach a private-safe provider.
Deterministic and auditable, in the same spirit as the honesty gate."""

import unittest

from .provider import (GeminiProvider, GroqProvider, OpenRouterProvider,
                       PaidGeminiProvider, StaticProvider)
from .trust import PrivateDataError, assert_safe_for_private


class InterlockTests(unittest.TestCase):
    def test_refuses_every_free_provider(self):
        for p in (GeminiProvider(), GroqProvider(), OpenRouterProvider()):
            with self.assertRaises(PrivateDataError):
                assert_safe_for_private(p)

    def test_passes_private_safe_providers(self):
        assert_safe_for_private(PaidGeminiProvider())   # must not raise
        assert_safe_for_private(StaticProvider("x"))

    def test_absent_flag_is_refused_not_assumed(self):
        class Bare:  # a provider that never declared itself
            pass
        with self.assertRaises(PrivateDataError):
            assert_safe_for_private(Bare())
```

**Step 2: Run to verify failure** — ModuleNotFoundError.

**Step 3: Implement `evals/trust.py`:**

```python
# evals/trust.py
"""The deterministic trust interlock: private code -> private-safe model ONLY.

Like the honesty gate, this is provable in code, never a judgement call: a
provider is private-safe iff it declares private_safe=True (set only at
construction from a dedicated paid-key env — see evals/provider.py). Anything
else, including a provider that never declared itself, is refused."""


class PrivateDataError(RuntimeError):
    """Raised instead of ever sending private code to a non-private-safe model."""


def assert_safe_for_private(provider) -> None:
    if not getattr(provider, "private_safe", False):
        raise PrivateDataError(
            f"{type(provider).__name__} is not private-safe: refusing to send "
            "private code to a model that may train on it")
```

**Step 4: Run to green** — `python3 -m unittest evals.test_trust -v`.

**Step 5: Commit.**
```bash
git add evals/trust.py evals/test_trust.py
git commit -m "feat(brain): deterministic trust interlock (private code -> no-train model only)"
```

## Task 7: Prove the paid writer on the eval board (live; skippable)

**Files:**
- Create: `evals/test_paid_writer_eval.py`

**Step 1:** Read `evals/test_gated_eval.py` first and mirror its structure
exactly (skip guards, corpus check, grading calls). The new test:
- `@unittest.skipUnless(os.environ.get("GEMINI_PAID_API_KEY") and CORPUS.exists(), ...)`
- Build `GatedPipeline` with `make_provider("gemini-paid")` over the committed
  **public** corpus, grade against the labelled set, and assert **groundedness ==
  1.0 and abstention recall == 1.0** and citation correctness ≥ the free
  baseline asserted in `test_gated_eval.py` (copy its exact threshold — do not
  invent a new one).

**Step 2:** Run without the key: `python3 -m unittest evals.test_paid_writer_eval -v`
→ `SKIPPED`. That is the offline green.

**Step 3:** When the owner sets `GEMINI_PAID_API_KEY`, run once for real and
paste the numbers into the commit message. **Do not claim the paid writer works
until this has actually run.**

**Step 4: Commit.**
```bash
git add evals/test_paid_writer_eval.py
git commit -m "test(brain): paid-writer board proof (gates 100%), self-skips without the paid key"
```

---

# BRICK D — Private-repo access + authenticated ingest

## Task 8: `repo_info` — the caller-scoped permission gate

**Files:**
- Create: `evals/github_access.py`
- Test: `evals/test_github_access.py` (create)

**Step 1: Failing tests** — `evals/test_github_access.py`:

```python
# evals/test_github_access.py
"""The private-repo permission gate: GET /repos/{owner}/{repo} AS THE CALLER.
200 -> {"private": bool}; anything else -> None (fail-safe refuse). Offline:
the opener is injected."""

import io
import json
import unittest
import urllib.error

from .github_access import repo_info


class _Resp(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener_returning(status, body):
    captured = {}

    def opener(req, timeout):
        captured["req"] = req
        return _Resp(status, body)

    return opener, captured


class RepoInfoTests(unittest.TestCase):
    def test_200_private_true(self):
        opener, _ = _opener_returning(200, b'{"private": true, "full_name": "o/r"}')
        self.assertEqual(repo_info("o/r", "tok", opener=opener), {"private": True})

    def test_200_public(self):
        opener, _ = _opener_returning(200, b'{"private": false}')
        self.assertEqual(repo_info("o/r", "tok", opener=opener), {"private": False})

    def test_sends_the_callers_token_as_bearer(self):
        opener, captured = _opener_returning(200, b'{"private": false}')
        repo_info("o/r", "the-token", opener=opener)
        self.assertEqual(captured["req"].get_header("Authorization"), "Bearer the-token")

    def test_404_refuses(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b""))
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_network_error_refuses(self):
        def opener(req, timeout):
            raise urllib.error.URLError("down")
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_garbage_body_refuses(self):
        opener, _ = _opener_returning(200, b"not json")
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_missing_private_field_refuses(self):
        opener, _ = _opener_returning(200, b'{"full_name": "o/r"}')
        self.assertIsNone(repo_info("o/r", "tok", opener=opener))

    def test_no_token_refuses_without_calling_out(self):
        def opener(req, timeout):
            raise AssertionError("must not call out without a token")
        self.assertIsNone(repo_info("o/r", "", opener=opener))


if __name__ == "__main__":
    unittest.main()
```

**Step 2:** Run → ModuleNotFoundError.

**Step 3: Implement `evals/github_access.py`:**

```python
# evals/github_access.py
"""Caller-scoped repo access check — the permission gate in front of private
ingest. We ask GitHub 'can THIS token read THIS repo?' and refuse on anything
but a clean 200 (fail safe, like the honesty gate). The same response tells us
whether the repo is private, which routes writer + storage. The token is used
in-memory for one request header; never logged, never stored."""

import json
import urllib.request

_API = "https://api.github.com/repos/"
_USER_AGENT = "icarus/0.1"


def _default_opener(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


def repo_info(repo: str, token: str, opener=None, timeout: float = 10.0):
    """-> {"private": bool} iff GitHub answers 200 with a boolean `private`
    field for this token; None on ANY other outcome (403, 404, network error,
    malformed body, missing token). Never raises."""
    if not repo or not token:
        return None
    opener = opener or _default_opener
    req = urllib.request.Request(
        _API + repo,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener(req, timeout) as resp:
            if getattr(resp, "status", None) != 200:
                return None
            data = json.loads(resp.read())
    except Exception:
        return None
    private = data.get("private") if isinstance(data, dict) else None
    if not isinstance(private, bool):
        return None
    return {"private": private}
```

**Step 4: Run to green.** **Step 5: Commit.**
```bash
git add evals/github_access.py evals/test_github_access.py
git commit -m "feat(brain): caller-scoped repo access gate (200-or-refuse, private flag)"
```

## Task 9: Leak-safe authenticated ingest

**Files:**
- Modify: `evals/ingest.py`
- Test: `evals/test_ingest_repo.py` (extend), `evals/test_ingest_args.py` (check)

**Step 1: Failing tests** (append to `evals/test_ingest_repo.py`; read the file
first and reuse its existing monkeypatch fixtures):

```python
class AuthenticatedIngestTests(unittest.TestCase):
    """The caller's token authenticates git+gh — via ENV ONLY. argv shows in
    `ps`, URLs land in git config: both are leaks."""

    def test_git_env_carries_basic_auth_never_argv(self):
        from .ingest import _git_env
        env = _git_env("SECRET-TOKEN")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.extraHeader")
        self.assertTrue(env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic "))
        self.assertNotIn("SECRET-TOKEN", env["GIT_CONFIG_VALUE_0"])  # b64, not raw
        import base64
        b64 = env["GIT_CONFIG_VALUE_0"].split()[-1]
        self.assertEqual(base64.b64decode(b64).decode(), "x-access-token:SECRET-TOKEN")

    def test_git_env_without_token_is_plain(self):
        import os
        from .ingest import _git_env
        self.assertNotIn("GIT_CONFIG_COUNT", set(_git_env(None)) - set(os.environ))

    def test_gh_env_sets_gh_token(self):
        from .ingest import _gh_env
        self.assertEqual(_gh_env("SECRET")["GH_TOKEN"], "SECRET")

    def test_token_reaches_subprocess_env_never_args(self):
        # Monkeypatch subprocess.run; drive ingest_repo(token=...) end to end
        # (reuse this file's existing fake-run fixtures) and assert:
        #   * no element of ANY `args` list contains "SECRET-TOKEN"
        #   * git calls got env with GIT_CONFIG_VALUE_0
        #   * gh calls got env with GH_TOKEN == "SECRET-TOKEN"
        ...
```

(Write the last test concretely against the file's existing fixture style —
`test_ingest_repo.py` already fakes `subprocess.run`; extend the fake to record
`kwargs.get("env")`.)

**Step 2:** Run → ImportError on `_git_env`.

**Step 3: Implement in `evals/ingest.py`:** add `import base64, os`; add the two
helpers exactly as tested:

```python
def _git_env(token=None):
    """Subprocess env for git. A token authenticates via GIT_CONFIG_* env
    (http.extraHeader with Basic x-access-token) — never argv (visible in ps),
    never the URL (lands in git config). The token is never logged."""
    env = dict(os.environ)
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        })
    return env


def _gh_env(token=None):
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token  # per-call, never the server's ambient identity
    return env
```

Then thread `token` through: `ingest_repo(repo, out_dir, commit=None,
code_dir="llm", token=None)`; `resolve_commit(repo, commit, token=None)` passes
`env=_git_env(token)` to `ls-remote`; `_gh_json(args, token=None)` passes
`env=_gh_env(token)`; `fetch_prs(repo, token=None)` / `fetch_issues(repo, ids,
token=None)` forward it; `fetch_code(repo, commit, code_dir, token=None)` passes
`env=_git_env(token)` to both `git clone` and `git checkout`. The CLI (`main`)
stays public-only — no `--token` flag; the demo passes the token
programmatically, and a token on a CLI line would land in shell history.

**Step 4:** `python3 -m unittest evals.test_ingest_repo evals.test_ingest_args -v`
→ green; full evals suite green.

**Step 5: Commit.**
```bash
git add evals/ingest.py evals/test_ingest_repo.py
git commit -m "feat(brain): ingest authenticates as the caller — token via env only, never argv/URL"
```

## Task 10: OAuth asks for the `repo` scope

**Files:**
- Modify: `demo/github_oauth.py:31` (the `scope` default)
- Test: `demo/test_github_oauth.py`

**Step 1:** In `demo/test_github_oauth.py`, find the authorize-url test and
change/extend it to assert `scope=repo` appears in the built URL (read the file
for the exact assertion style). **Step 2:** run → fails (scope is `read:user`).
**Step 3:** change the default: `scope: str = "repo"`, with the comment:
*"`repo` = read access to the user's private repos (GitHub has no finer OAuth
read scope). Broad by necessity for the beta; the narrow path is a GitHub App
with per-repo selection — deferred, see the scoping doc. Existing sign-ins hold
`read:user` tokens: users must sign out/in again before connecting a private
repo."* **Step 4:** demo suite green. **Step 5:**
```bash
git add demo/github_oauth.py demo/test_github_oauth.py
git commit -m "feat(brain): request the repo OAuth scope so the caller's token can read their private repos"
```

## Task 11: The Library learns private; the server routes it

**Files:**
- Modify: `demo/library.py`, `demo/registry.py`, `demo/server.py`
- Test: `demo/test_library.py`, `demo/test_server.py`

**Step 1: Failing library tests** (append to `demo/test_library.py`; note the
fake ingest fns in this file gain a `token=None` kwarg — update them):

```python
class PrivateConnectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.default_dir = root / "default"
        _seed_corpus(self.default_dir, "simonw/llm")
        self.cache_root = root / "u1" / "cache"
        self.ingest_calls = []

        def fake_ingest(repo, out_dir, commit=None, code_dir="llm", token=None):
            self.ingest_calls.append((repo, str(out_dir), token))
            _seed_corpus(out_dir, repo)
            return {"pr": 1, "issue": 0, "code": 0}

        self.private_built = []

        def fake_private_build(corpus_dir):
            self.private_built.append(str(corpus_dir))
            return f"private-pipeline::{corpus_dir}"

        self.lib = Library(self.default_dir, self.cache_root, "simonw/llm",
                           build_pipeline=lambda d: f"pipeline::{d}",
                           ingest_fn=fake_ingest,
                           build_private_pipeline=fake_private_build,
                           private_ready=lambda: True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_private_connect_uses_private_path_token_and_pipeline(self):
        self.lib.connect_sync("octo/secret", token="tok", private=True)
        repo, out_dir, token = self.ingest_calls[0]
        self.assertEqual(token, "tok")
        self.assertIn("/private/", out_dir.replace("\\", "/"))  # not the public cache
        s = self.lib.status_snapshot()
        self.assertEqual(s["repo"], "octo/secret")
        self.assertTrue(s["private"])
        self.assertTrue(str(self.lib.current_pipeline()).startswith("private-pipeline::"))

    def test_public_connect_is_unchanged_and_not_private(self):
        self.lib.connect_sync("octo/open")
        self.assertIsNone(self.ingest_calls[0][2])   # no token spent on public
        self.assertFalse(self.lib.status_snapshot()["private"])

    def test_private_connect_without_paid_writer_refuses_before_ingest(self):
        self.lib._private_ready = lambda: False
        self.lib.connect_sync("octo/secret", token="tok", private=True)
        self.assertEqual(self.ingest_calls, [])       # refused BEFORE cloning
        s = self.lib.status_snapshot()
        self.assertEqual(s["state"], "error")
        self.assertNotIn("tok", s["error"] or "")

    def test_token_never_appears_in_status(self):
        self.lib.connect_sync("octo/secret", token="super-secret", private=True)
        self.assertNotIn("super-secret", json.dumps(self.lib.status_snapshot()))
```

**Step 2:** Run → TypeError (unexpected kwargs).

**Step 3: Implement.**

`demo/library.py` — extend the constructor and connect path (surgical; existing
public flow byte-identical when `private=False`):

```python
def _default_build_private_pipeline(corpus_dir):
    # The interlock is checked at construction — the single chokepoint where the
    # provider is fixed. gemini-paid is the only writer allowed private code.
    from evals.trust import assert_safe_for_private
    provider = make_provider("gemini-paid")
    assert_safe_for_private(provider)
    chunks = load_chunks(Path(corpus_dir) / "chunks.jsonl")
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


def _default_private_ready():
    return has_provider_key("gemini-paid")
```

Constructor gains `build_private_pipeline=_default_build_private_pipeline,
private_ready=_default_private_ready`; store both; add `self._private = False`;
derive `self._private_root = Path(cache_root).parent / "private"`.

`_resolve(repo, private=False)`:
```python
        if repo == self._default_repo:
            return self._default_dir, False
        base = self._private_root if private else self._cache_root
        cache = base / _slug(repo)
        return cache, not (cache / "chunks.jsonl").exists()
```

`connect_sync(self, repo, token=None, private=False)`:
- **Before anything else**, if `private and not self._private_ready()`: set
  status `error` with the generic message
  `"Private repos aren't available yet on this brain."` and return the snapshot
  (never clone code we can't answer over).
- `corpus_dir, needs_ingest = self._resolve(repo, private)`.
- Ingest call becomes `self._ingest_fn(repo, corpus_dir, code_dir=".", token=token)`.
- Build: `builder = self._build_private_pipeline if private else self._build_pipeline`.
- On success, also set `self._private = private` under the lock; snapshot gains
  `"private": self._private`. (Swift `Codable` ignores unknown JSON keys — the
  Mac app is unaffected until Brick G surfaces it.)
- The token is a **local variable only** — assert nothing stores it on `self`.

`demo/registry.py` — pass-through: constructor gains
`build_private_pipeline=None, private_ready=None`; forward to each `Library`
when not None.

`demo/server.py` — the `/connect` route decides, *synchronously* (the GitHub
call is sub-second and lets us 403 before spawning work):

```python
            elif self.path == "/connect":
                ...  # existing body/regex validation unchanged
                repo = repo.strip()
                token = bearer_token(self.headers)
                private = False
                if require_auth:
                    # Cloud mode: prove the CALLER can read the repo, and learn
                    # its visibility, before any clone. Fail-safe refuse.
                    info = github_access.repo_info(repo, token)
                    if info is None:
                        self._send_json(403, {"error": "that repo doesn't exist or your GitHub account can't read it"})
                        return
                    private = info["private"]
                threading.Thread(target=lib.connect_sync,
                                 args=(repo,),
                                 kwargs={"token": token if private else None,
                                         "private": private},
                                 daemon=True).start()
                self._send_json(202, {"state": "indexing", "repo": repo})
```

(import `from evals import github_access`). Add a server test: with
`require_auth=True` and a patched `repo_info` returning `None`, `/connect` is
403 and the stub library records no connect; returning `{"private": True}`
spawns a connect with `private=True` (record kwargs on the stub —
`_StubLibrary.connect_sync` gains `(self, repo, token=None, private=False)` and
appends the triple).

**Step 4:** Full demo + evals suites green.

**Step 5: Commit.**
```bash
git add demo/library.py demo/registry.py demo/server.py demo/test_library.py demo/test_server.py
git commit -m "feat(brain): private connect — caller-verified, token-authed ingest, paid pipeline, private storage"
```

## Task 12: Live private proof (skippable)

**Files:**
- Create: `evals/test_private_ingest_live.py`

Skip guard: `RUN_PRIVATE_INGEST=1` + `ICARUS_TEST_PRIVATE_REPO` (an `owner/name`
the token can read) + `GITHUB_TOKEN` + `GEMINI_PAID_API_KEY`, else skip. Body:
1. `repo_info(repo, token)` → `{"private": True}`.
2. `ingest_repo(repo, tmpdir, code_dir=".", token=token)` → chunks + meta
   written, counts non-zero. (This also live-verifies the Basic
   x-access-token auth actually clones — the one thing offline tests can't.)
3. Build the private pipeline over it; ask one question; assert `verdict` in
   `{"answer", "unknown"}` and, if "answer", citations ⊆ retrieved.
4. Swap in `GeminiProvider()` (free) via the interlock path → `PrivateDataError`.

Run: `python3 -m unittest evals.test_private_ingest_live -v` → SKIPPED offline.
Commit: `test(brain): live private-repo proof (access, authed clone, paid answer, interlock) — self-skips`.

---

# BRICK E — The proofs (isolation + egress invariants)

## Task 13: Cross-user isolation suite

**Files:**
- Create: `demo/test_isolation.py`

Server-level, offline: a **real** `LibraryRegistry` (temp `storage_root`, fake
build/ingest fns as in `test_registry.py`) behind a real `_ServerFixture` with
`require_auth=True` and `StaticTokenVerifier({"tok-a": "1", "tok-b": "2"})`.
Helper `_ask/_status/_connect(base, token, ...)` wrappers that set the bearer.
Assert at the HTTP boundary (the strongest place):

1. **connect isolation:** A connects `octo/xrepo` (wait for A's `/status` to be
   ready by polling ≤2 s); B's `/status` still shows the default repo, and B's
   `/ask` still answers from the default pipeline.
2. **storage isolation:** files exist under `storage/1/…`, nothing under
   `storage/2/…`; the two paths are disjoint.
3. **no identity, no state:** an unauthenticated `/status` shows only the
   default; `/ask` and `/connect` without a token are 401 (already covered, but
   assert here as the isolation property).
4. **disconnect isolation:** A `POST /disconnect` → `storage/1` is gone,
   `storage/2` intact, B's status unchanged; A's next `/status` is the default.
5. **provenance isolation:** after A's connect, A's `/ask` payload cites A's
   repo URLs, B's cites the default's (build the fake pipelines to return
   distinguishable `Result`s).

Commit: `test(brain): cross-user isolation proven at the HTTP boundary`.

## Task 14: Egress invariants suite

**Files:**
- Create: `evals/test_egress_invariants.py`

Offline. A `SpyProvider(Provider)` that records every `complete()` prompt and
carries a settable `private_safe`. Assert:

1. **Private path egress:** build the private pipeline machinery from
   `demo/library.py` with a private-safe spy; connect+ask over a corpus
   containing the sentinel text `"XYZZY-PRIVATE-42"`; the sentinel appears
   **only** in the spy's prompts (it must reach the writer — that's the
   product), and no other provider instance was ever called.
2. **Interlock in the wired path:** the same machinery handed a
   `private_safe=False` spy raises `PrivateDataError` and the spy records
   **zero** prompts (nothing left before the refusal).
3. **No judge in the serve path:** `demo/library.py` and `demo/server.py` never
   import `evals.judge` — assert
   `"judge" not in Path("demo/library.py").read_text()` (and server.py). Crude
   but effective: the serve-path egress surface stays writer-only, and this
   test fails loudly if someone wires the judge in.
4. **Git hygiene:** `subprocess.run(["git", "check-ignore", "-q", "data/1001/private/x/chunks.jsonl"])`
   returns 0 (the per-user tree is ignored), and
   `scripts/scan_secrets.sh` still exits 0 on the tracked tree.

Commit: `test(brain): egress invariants — private text reaches only the private-safe writer`.

---

# BRICK F — Ops, env, docs

## Task 15: Per-identity rate limiting on /ask and /connect

**Files:**
- Create: `demo/ratelimit.py`
- Modify: `demo/server.py`
- Test: `demo/test_ratelimit.py` (create) + one server-level 429 test

`demo/ratelimit.py`:

```python
# demo/ratelimit.py
"""Per-key sliding-window rate limiter. Ingest shells out to git/gh and the
writer bills per request — bound both per identity. Stdlib, thread-safe."""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self._limit, self._window = limit, window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self._window:
                q.popleft()
            if len(q) >= self._limit:
                return False
            q.append(now)
            return True
```

Tests: under the limit → True; at the limit → False; a different key is
unaffected; after the window slides, allowed again (drive time with a
monkeypatched `time.time`, no sleeping). Server wiring: `make_handler` gains
`ask_limiter=None, connect_limiter=None` (defaults `RateLimiter(30, 60)` and
`RateLimiter(5, 600)` built inside `make_handler`); after identity resolution on
`/ask`/`/connect`, `if not limiter.allow(identity): 429 {"error": "slow down — try again in a minute"}`.
Server test injects `RateLimiter(1, 60)` and asserts the second POST is 429.
Commit: `feat(brain): per-identity rate limits on /ask and /connect`.

## Task 16: Env plumbing, deploy config, docs, indexes

**Files:**
- Modify: `.env.example`, `render.yaml`, `CLAUDE.md`, `docs/DISTRIBUTION.md`,
  `docs/HANDOFF.md`, `general_index.md`, `detailed_index.md`

- `.env.example`: add `GEMINI_PAID_API_KEY=` (comment: *billing-enabled; the
  private-repo writer; may equal GEMINI_API_KEY only if that key is billed —
  placing it here is the attestation*) and `ICARUS_STORAGE_ROOT=` (optional,
  defaults to `<repo>/data`).
- `render.yaml`: add `GEMINI_PAID_API_KEY` with `sync: false`;
  `ICARUS_STORAGE_ROOT=/opt/render/project/src/data` (explicit even though
  ephemeral — free-tier decision recorded in the scoping doc).
- `CLAUDE.md` Commands section: the private-repo recipe (sign in with the
  `repo`-scoped login → connect a private `owner/name` → paid writer answers;
  `POST /disconnect` deletes your data), plus the loud warnings (never commit
  `data/`; public → free writer, private → paid only; token via env only).
- `docs/DISTRIBUTION.md`: the new Render env vars + "users must re-sign-in once
  for the repo scope".
- Regenerate both indexes (new files: `demo/registry.py`, `demo/ratelimit.py`,
  `evals/trust.py`, `evals/github_access.py`, the new test modules, this plan).
- Final gate: **both full suites + `swift test` (nothing Swift changed, prove
  it)**, `bash scripts/scan_secrets.sh`, then commit:
  `docs(brain): private-repo env, deploy config, recipes; regenerate indexes`.

---

# BRICK G — Mac app surface (outline only; build after the brain is live-proven)

Scope for its own plan later — the brain changes above are app-compatible
(unknown JSON keys are ignored by Swift `Codable`; the authorize URL comes from
the brain, so the scope change needs **zero** app code). The app brick is:
1. `IcarusKit/Models.swift`: decode `private: Bool?` in `RepoStatus`.
2. `BrainClient.disconnect()` → `POST /disconnect`; a "Disconnect & delete my
   data" control in `SidebarView`/`SetupView`.
3. A visible **Private** badge (and "paid no-training writer" line) when
   `status.private == true` — honesty in the UI.
4. Sign-out/in prompt when `/connect` returns 403 with an old-scope token.
5. `swift test` additions mirroring each.

---

## Definition of done (whole plan)

- Both Python suites green offline; live tests skip cleanly without keys and
  pass with them (paid-writer board: **gates 100%**; private ingest: cited
  answer + interlock refusal — actually run, numbers in the commit).
- Two signed-in users demonstrably cannot see each other's repo/corpus/answers
  (Task 13 at the HTTP boundary).
- A private connect is refused without proof the caller can read the repo, and
  refused before ingest when the paid writer isn't configured.
- The token never appears in argv, URLs, logs, status JSON, or disk.
- `data/` is git-ignored; the secrets scan passes; the honesty gate
  (`evals/gate.py`) is **byte-for-byte unchanged** (`git diff --stat` proves it).
- No new dependencies; `swift test` still passes untouched.
