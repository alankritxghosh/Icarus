# demo/server.py
"""A minimal local web face over the gated brain. Stdlib http.server only.

GET  /        -> the static demo page (demo/index.html)
GET  /health  -> {"ok": true, "repo": ..., "commit": ...} -- liveness + provenance
GET  /status  -> the active repo + switch status, and a `freshness` block
                 saying whether the index still matches the repository
                 (demo/freshness.py; unknown is reported, never omitted)
GET  /map     -> what Icarus INDEXED for the active repo (demo/repo_map.py)
GET  /onboarding -> the guided tour plan; POST {"step": ...} -> one cited step
GET  /briefing -> what changed since this caller was last here (pure);
                 POST /briefing acknowledges it and moves the anchor forward
                 (demo/visits.py; docs/decisions/2026-07-30-returning-user-state.md)
POST /ask     -> {"question": "..."} -> the build_payload JSON for the page
POST /auth/agent/session -> short-lived read-only token for the active repo
POST /connect -> {"repo": "owner/name"[, "refresh": true]} -> index/switch to it
POST /disconnect -> forget the caller's library and delete their on-disk storage

The active pipeline lives in a Library (demo/library.py); the handler is a thin
shell over it. /connect runs in a background thread so the request returns
immediately and the page polls /status. No brain code changes -- packaging only.
The public-repository alpha uses one Gemini writer.
Run: GEMINI_PAID_API_KEY=... python3 -m demo.server
"""

import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from evals.corpus_meta import load_meta
from evals.env_file import load_env_file

from . import posthog_capture
from .freshness import FreshnessChecker
from .ledger import Ledger
from .memory_writer import GitHubMemoryWriter, MemoryWriteError
from evals.entities import build_entity_index
from evals.ingest import fetch_pr_diff
from evals import investigator as _investigator
from .investigations import ConversationStore, refers_back
from .structure import build_structure
from evals.context_package import build_context_package
from .payload import (build_context_payload, build_investigation_payload,
                     build_payload)
from .repo_map import build_map
from .visits import VisitStore
from . import onboarding
from .registry import LibraryRegistry
from .auth import bearer_token, GitHubTokenVerifier, RepoAccessVerifier
from .agent_sessions import AgentSessionStore
from . import github_oauth
from .ratelimit import RateLimiter
from evals import github_access

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
CORPUS_DIR = ROOT.parent / "evals" / "corpus"
CORPUS_META = CORPUS_DIR / "meta.json"
QUESTIONS = ROOT.parent / "evals" / "phase1_questions.json"
INDEX_HTML = ROOT / "index.html"

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GAP_ID_RE = re.compile(r"^[0-9a-f]{64}$")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


def _parse_allowed_hosts(raw):
    """Parse ICARUS_ALLOWED_HOSTS (comma-separated) into a set, or None for the
    loopback-only default. A '*' entry means "trust the platform's TLS proxy and
    rely on the GitHub bearer gate" — used when the brain runs in the cloud."""
    if not raw:
        return None
    hosts = {h.strip() for h in raw.split(",") if h.strip()}
    return hosts or None


class _RegistryWarming(Exception):
    """Raised by _LazyRegistry while the real LibraryRegistry is still
    building on a background thread (see _LazyRegistry's docstring)."""


class _LazyRegistry:
    """Builds a LibraryRegistry on a background thread so `serve()` can bind
    the listening socket immediately instead of blocking on it first.

    LibraryRegistry's constructor cold-embeds the ENTIRE default corpus via
    the local semantic embedder whenever no on-disk vector cache exists --
    true on every fresh checkout/deploy, since the cache is git-ignored (see
    evals/vector_cache.py) and, on a PaaS like Render, the disk is wiped on
    every deploy/restart/idle-sleep too. That embed can take long enough that
    a PaaS's post-bind port-scan gate times out waiting for it, which fails
    the deploy outright -- discovered live deploying Brick D's branch to
    Render (docs/HANDOFF.md's D5 section). Binding first and building the
    registry in the background fixes that: `library_for`/`disconnect` raise
    `_RegistryWarming` until the build finishes, which the handler turns into
    an honest 'still starting up' response (200 for /health so a liveness
    check doesn't flap during normal warmup, 503 for routes that actually
    need a working registry) rather than hanging the whole process."""

    def __init__(self, build):
        self._registry = None
        self._error = None
        threading.Thread(target=self._build, args=(build,), daemon=True).start()

    def _build(self, build):
        try:
            self._registry = build()
        except Exception as e:  # surfaced on every call via _get, never swallowed
            self._error = e

    def _get(self):
        if self._error is not None:
            raise self._error
        if self._registry is None:
            raise _RegistryWarming()
        return self._registry

    def library_for(self, user_id):
        return self._get().library_for(user_id)

    def disconnect(self, user_id):
        return self._get().disconnect(user_id)


def _resolve_storage_root(raw, default):
    """ICARUS_STORAGE_ROOT, falling back to `default` when unset OR set-but-
    blank (a PaaS env-var UI can easily leave a value blank rather than unset;
    `os.environ.get(key, default)` alone would silently resolve that to the
    cwd instead of the intended default)."""
    return Path(raw or default)


def make_handler(registry, html_path: str, require_auth: bool = False, verifier=None,
                 oauth=None, allowed_hosts=None, ask_limiter=None, connect_limiter=None,
                 sync_connect: bool = False, background_upgrade: bool = False,
                 access_verifier=None, default_repo=None, ledger=None,
                 refresh_limiter=None, freshness=None, visits=None,
                 commits_since=None, agent_sessions=None, agent_repo_info=None,
                 agent_session_limiter=None, memory_writer=None,
                 memory_limiter=None, conversations=None, entity_index=None,
                 investigate_limiter=None):
    """Build a request handler bound to a library registry (resolves the active-
    repo state per caller identity; see `_identity`).

    `require_auth` gates /ask and /connect behind a valid GitHub bearer token
    (verified by `verifier`); the plain web demo leaves it False and relies on
    the loopback bind + Host/Origin guard. `oauth` (an OAuthFlow) enables the web
    GitHub login endpoints; None leaves them off. `allowed_hosts` overrides the
    loopback-only Host allow-list (a set); include '*' to accept any Host/Origin
    (cloud mode — the bearer gate becomes the real boundary). None = loopback only.

    `ask_limiter`/`connect_limiter` are per-identity `RateLimiter`s (see
    `demo/ratelimit.py`) bounding how often a caller can hit the LLM writer
    (/ask) or spawn a clone/ingest (/connect); defaults are generous real-world
    limits so they never fire in normal use or in tests that make a handful of
    requests.

    `sync_connect` changes how /connect is served -- see its use below. Default
    (False) matches every host tried before it: a real VM/box (local, Oracle)
    where a background thread just keeps running after the response returns.

    `access_verifier` (a `RepoAccessVerifier`) is the entitlement check on READS
    of the active repo -- see `_entitled`. It exists because a shared per-repo
    index means the storage layout is no longer the isolation. `default_repo` is
    the built-in public demo, exempted from that check.

    `ledger` (a `demo.ledger.Ledger`) records each ask against the repo, so a
    team accumulates one shared record -- and, in its unknowns, a map of what
    the organisation never wrote down. None disables recording entirely.

    `refresh_limiter` bounds `POST /connect {"refresh": true}` SEPARATELY from
    ordinary connects, and much more tightly. They are not the same operation:
    an ordinary connect to an already-cached repo is a ~1s cache hit, while a
    refresh is a full re-ingest -- 283 seconds measured live on production --
    that also republishes a corpus other entitled readers are using
    concurrently. Sharing one budget would let a caller spend an allowance
    sized for cache hits on minutes of CPU each.

    `freshness` (a `demo.freshness.FreshnessChecker`) adds a `freshness` block
    to /status saying whether the index still matches the repository. None
    still reports the block, with everything unknown -- never omitted, because
    a missing field renders as "no banner", which reads as up to date.

    `visits` (a `demo.visits.VisitStore`) enables `GET/POST /briefing` --
    returning-user state, implementing
    `docs/decisions/2026-07-30-returning-user-state.md`. None disables the
    endpoint entirely (404), so a deployment that has not accepted that
    decision stores nothing about anyone. `commits_since(repo, base, head,
    token)` computes how much moved between two commits; it defaults to
    `evals.github_access.commits_between` and is injectable for tests.

    `agent_sessions` enables short-lived, read-only bearer tokens for coding
    agents, covering public AND private repositories since 2026-08-07 (see
    docs/decisions/2026-08-07-mcp-private-repository-access.md).
    `agent_repo_info` verifies the signed-in GitHub caller can READ the active
    repository when they mint one -- authorization survived that decision, the
    public-only requirement did not. Agent sessions are bound to that caller
    and repository and can reach only /status, /ask, and /explain.

    `memory_writer` enables the explicit engineering-memory write: one branch,
    one new Markdown file, and one pull request. It receives the caller's
    verified GitHub bearer in memory and never receives an identity to persist.
    """
    hosts = set(allowed_hosts) if allowed_hosts is not None else set(_LOOPBACK_HOSTS)
    wildcard = "*" in hosts
    ask_limiter = ask_limiter or RateLimiter(30, 60)          # 30 asks/min
    connect_limiter = connect_limiter or RateLimiter(5, 600)  # 5 connects/10min
    refresh_limiter = refresh_limiter or RateLimiter(2, 3600)  # 2 re-ingests/hour
    agent_session_limiter = agent_session_limiter or RateLimiter(10, 60)
    memory_limiter = memory_limiter or RateLimiter(5, 3600)
    commits_since = commits_since or github_access.commits_between
    conversations = conversations if conversations is not None else ConversationStore()
    # One investigation makes SEVERAL billed calls where an ask makes one, so it
    # cannot share /ask's per-request allowance and still bound spend honestly:
    # 30 investigations a minute is ~300 provider calls, not 30. Its own, much
    # smaller allowance keeps the billed rate in the same place /ask puts it.
    investigate_limiter = investigate_limiter or RateLimiter(3, 60)   # 3/min

    if entity_index is None:
        # The relationship index an investigation traverses. Derived from the
        # chunks already in memory (evals/entities.py), so it needs no ingest and
        # no store -- but it IS pure work over the whole corpus, so it is cached
        # per content-addressed corpus rather than rebuilt for every follow-up
        # question. A same-SHA discussion refresh changes that fingerprint.
        _entity_cache = {}
        _entity_lock = threading.Lock()

        def entity_index(lib, snapshot=None):
            # Keyed by CORPUS identity, not just HEAD: ingest includes mutable
            # discussion, so a same-SHA refresh can publish different evidence.
            key = snapshot.corpus_id if snapshot is not None else lib.provenance()
            with _entity_lock:
                hit = _entity_cache.get(key)
            if hit is not None:
                return hit
            pipeline = snapshot.pipeline if snapshot is not None else lib.current_pipeline()
            chunks = pipeline.indexed_chunks()
            built = build_entity_index(chunks, structure=build_structure(chunks))
            with _entity_lock:
                _entity_cache.clear()   # one repo is active at a time per caller
                _entity_cache[key] = built
            return built

    class Handler(BaseHTTPRequestHandler):
        _MAX_BODY = 64 * 1024
        # Per-connection socket timeout (defense in depth for M1): a client that
        # opens a connection and then dribbles or stalls its body can't hold a
        # server thread open indefinitely -- a blocking recv past this is cut.
        # Well above any legitimate 64KB body upload; only bites a stalled client.
        timeout = 60

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, code, body: bytes, content_type: str, headers=None):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code, obj, headers=None, capture_extra=None):
            self._capture_product_event(code, obj, capture_extra)
            self._send(code, json.dumps(obj).encode(), "application/json", headers)

        # Path -> PostHog event name for the handful of real product actions.
        # Deliberately a small whitelist, not every response: a health check or
        # a validation error is not usage worth counting.
        _CAPTURED_EVENTS = {
            "/ask": "question_asked",
            "/explain": "question_asked",
            "/investigate": "question_asked",
            "/context": "context_requested",
            "/connect": "repo_connected",
        }
        # Paths where the question + cited code evidence are shared by default
        # -- see CLAUDE.md's dated 2026-08-13 pre-customer-alpha exception.
        # /context and /connect never carry a single question, so they stay
        # counts-only regardless.
        _CONTENT_SHARED_PATHS = {"/ask", "/explain", "/investigate"}

        def _capture_product_event(self, code, obj, capture_extra=None):
            event = self._CAPTURED_EVENTS.get(self.path)
            if event is None or not (200 <= code < 300):
                return
            try:
                identity, kind, _grant = self._principal()
            except Exception:
                return
            # MCP always authenticates via an agent session (see
            # demo/auth.py/agent_sessions.py) -- that's already a reliable
            # surface signal with no MCP-side code change needed. Everything
            # else is GitHub-authenticated the same way, so a client-supplied
            # header is what tells the Mac app apart from the extension; a
            # caller that sends neither (the plain web demo) is "web".
            surface = "mcp" if kind == "agent" else (
                self.headers.get("X-Icarus-Client") or "web")
            repo = obj.get("repo") if isinstance(obj, dict) else None
            properties = {
                "surface": surface,
                "repo": repo,
                "endpoint": self.path,
            }
            if (self._share_content() and self.path in self._CONTENT_SHARED_PATHS
                    and isinstance(obj, dict)):
                properties["question"] = (capture_extra or {}).get("question")
                properties["answer"] = obj.get("answer")
                properties["evidence"] = [
                    {"ref": c.get("ref"), "excerpt": c.get("excerpt")}
                    for c in obj.get("citations", []) or []
                ]
            posthog_capture.capture(event, identity, properties)

        def _share_content(self) -> bool:
            """Counts-only unless the caller EXPLICITLY opts in.

            Reversed 2026-08-14 (Alankrit) from the dated 2026-08-13
            exception, which shared question/answer/evidence by default with
            an opt-out header. Raised in review: that exception was written
            for this endpoint when nothing external was connected, but the
            MCP surface now serves PRIVATE repositories and no client -- the
            two MCP adapters, the extension, the web page, the Mac app --
            ever sent the opt-out. So configuring the production PostHog
            token exported private questions, answers and cited code
            automatically. A default should not be able to decide that.

            Fails CLOSED on anything unexpected: only the exact string "1"
            opts in, so a malformed or truthy-looking value cannot turn
            content sharing on by accident. A client that wants to opt in
            must SEND "1" -- absence is no longer consent.
            """
            return self.headers.get("X-Icarus-Share-Content", "") == "1"

        def _content_length(self) -> int:
            """Validated body length. Rejects a NEGATIVE Content-Length (M1: a
            negative value slips past a `> _MAX_BODY` check and turns
            `rfile.read(length)` into a blocking `read(-1)` that holds the thread
            until the socket closes), a non-integer value (which would otherwise
            raise an uncaught ValueError and drop the connection), and an
            oversized one. Raises ValueError -- callers already treat that as a
            4xx."""
            raw = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw)
            except ValueError:
                raise ValueError("malformed Content-Length")
            if length < 0 or length > self._MAX_BODY:
                raise ValueError("bad Content-Length")
            return length

        def _body(self):
            length = self._content_length()
            return json.loads(self.rfile.read(length) or b"{}")

        def _authorized(self) -> bool:
            """Loopback-only Host + same-origin (when a browser sends Origin).
            Defeats DNS rebinding (attacker's hostname in Host) and cross-site
            POST from a website (attacker's Origin).

            In cloud mode (allowed_hosts contains '*') this check is skipped: the
            platform terminates TLS on a hostname we don't control, and /ask +
            /connect are already gated by the GitHub bearer token — which a cross-
            site script cannot forge — so the Host/Origin guard adds nothing."""
            if wildcard:
                return True
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in hosts:
                return False
            origin = self.headers.get("Origin")
            if origin is not None:
                oh = urlparse(origin).hostname or ""
                if oh not in hosts:
                    return False
            return True

        LOCAL_USER = "local"

        def _principal(self):
            """Return (identity, credential kind, agent grant), once per request."""
            if "_principal_cache" in self.__dict__:
                return self._principal_cache
            if not require_auth:
                principal = (self.LOCAL_USER, "local", None)
                self._principal_cache = principal
                return principal
            token = bearer_token(self.headers)
            grant = agent_sessions.verify(token) if agent_sessions is not None else None
            if grant is not None:
                principal = (grant.identity, "agent", grant)
            else:
                identity = verifier.verify(token) if token and verifier is not None else None
                principal = (identity, "github" if identity is not None else None, None)
            self._principal_cache = principal
            return principal

        def _identity(self) -> str | None:
            """Verified caller identity, or None when authentication fails."""
            return self._principal()[0]

        def _github_token(self):
            """Return a bearer only when it was verified as a GitHub credential."""
            return bearer_token(self.headers) if self._principal()[1] == "github" else None

        def _agent_repo_allowed(self, lib, grant) -> bool:
            """An agent grant cannot follow its owner when they switch repos.

            Privacy is deliberately NOT checked here (2026-08-07, see
            docs/decisions/2026-08-07-mcp-private-repository-access.md). The
            binding that matters is grant-to-repo: a grant minted for one repo
            must never answer about whichever repo its owner switched to since.
            That is what this enforces, and it holds for private repos too.
            """
            if grant is None:
                return False
            snapshot = lib.status_snapshot() or {}
            repo = snapshot.get("repo")
            return (
                isinstance(repo, str)
                and repo.casefold() == grant.repo.casefold()
            )

        def _freshness_of(self, lib, snapshot) -> dict:
            """Does the connected index still match the repository?

            Never raises and never omits the block. Staleness is a nicety;
            the connected-repo status is not, so a GitHub outage degrades this
            to "unknown" rather than taking /status down with it. And unknown
            is reported EXPLICITLY -- a missing field renders as no banner,
            which a user reads as "up to date", the one thing this must never
            imply without having checked.
            """
            # The committed demo corpus is frozen ON PURPOSE -- it is the
            # reproducible eval board, and `Library.connect_sync` exempts it
            # from every re-ingest path. So it is permanently behind upstream
            # (68 commits, measured live). The numbers below stay true and
            # nothing is hidden; `pinned` is what stops a deliberate decision
            # reading as neglect, and stops a client offering a refresh that
            # is forbidden by design.
            pinned = bool(default_repo) and snapshot.get("repo") == default_repo
            unknown = {"up_to_date": None, "behind_by": None,
                       "head_commit": None, "checked_at": None, "pinned": pinned}
            if freshness is None:
                return unknown
            try:
                result = dict(freshness.check(snapshot.get("repo"), snapshot.get("commit"),
                                              self._github_token()))
            except Exception:  # noqa: BLE001 -- see docstring: never break /status
                return unknown
            result["pinned"] = pinned
            return result

        def _entitled(self, lib) -> bool:
            """May this caller READ the library's currently-active repo?

            A verified identity is not the same as entitlement. Once a repo's
            corpus is shared between everyone who can read it, "whose directory
            is it in" stops answering that question and this does -- by asking
            GitHub, which is the authority on repo access (see
            demo/auth.RepoAccessVerifier).

            Two deliberate exemptions:
            - Auth off means a single local operator on loopback. There is no
              tenancy to enforce, and demanding a GitHub token would break local
              development for no gain.
            - The built-in demo repo is public and identical for everyone, so
              proving entitlement to it would burn a GitHub API call to confirm
              something already public.

            Every OTHER repo is checked, including ones recorded as public. That
            is deliberate: a repo can be made private after it was indexed, and
            re-asking GitHub each time is what contains that, where trusting the
            visibility we recorded at connect time would not.
            """
            if not require_auth:
                return True
            _identity, kind, grant = self._principal()
            if kind == "agent":
                return self._agent_repo_allowed(lib, grant)
            if access_verifier is None:
                return True
            repo = (lib.status_snapshot() or {}).get("repo")
            if not repo or repo == default_repo:
                return True
            return access_verifier.can_read(repo, self._github_token())

        def do_GET(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            route = urlparse(self.path).path
            if self._principal()[1] == "agent" and route != "/status":
                self._send_json(403, {"error": "agent sessions are read-only and route-scoped"})
                return
            if route == "/":
                self._send(200, Path(html_path).read_bytes(), "text/html; charset=utf-8")
            elif route == "/health":
                try:
                    lib = registry.library_for(self._identity())
                    repo, commit = lib.provenance()
                    self._send_json(200, {"ok": True, "repo": repo, "commit": commit})
                except _RegistryWarming:
                    # 200, not 503: the process is alive, just still cold-embedding
                    # the default corpus -- a PaaS liveness check shouldn't flap
                    # (and possibly restart-loop the container) during normal warmup.
                    self._send_json(200, {"ok": True, "state": "starting"})
            elif route == "/status":
                try:
                    lib = registry.library_for(self._identity())
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                    return
                if self._principal()[1] == "agent" and not self._entitled(lib):
                    self._send_json(403, {"error": "agent session is not valid for the active repo"})
                    return
                snapshot = lib.status_snapshot()
                snapshot["freshness"] = self._freshness_of(lib, snapshot)
                self._send_json(200, snapshot)
            elif route == "/briefing":
                self._handle_briefing(mutate=False)
            elif route == "/ledger":
                # The team's questions about their own code -- at least as
                # sensitive as the corpus, so guarded by the same check rather
                # than a weaker one.
                identity = self._identity()
                if require_auth and identity is None:
                    self._send_json(401, {"error": "sign in with GitHub to continue"})
                    return
                if ledger is None:
                    self._send_json(404, {"error": "not found"})
                    return
                try:
                    lib = registry.library_for(identity)
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                    return
                if not self._entitled(lib):
                    self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                    return
                repo, _commit = lib.provenance()
                q = parse_qs(urlparse(self.path).query)
                lifecycle = q.get("gaps", ["0"])[0] not in ("0", "", "false")
                if lifecycle:
                    include_resolved = q.get("resolved", ["0"])[0] not in ("0", "", "false")
                    self._send_json(200, {
                        "repo": repo,
                        "gaps": ledger.gaps(repo, include_resolved=include_resolved),
                    })
                    return
                unknowns = q.get("unknowns", ["0"])[0] not in ("0", "", "false")
                self._send_json(200, {
                    "repo": repo,
                    "entries": ledger.entries(repo, unknowns_only=unknowns),
                })
            elif route == "/map":
                # What Icarus INDEXED -- the first thing it says about a repo
                # before anyone asks a question. Guarded exactly like /ledger:
                # a private repo's file paths are at least as sensitive as the
                # answers drawn from them, so the map never sits behind a
                # weaker gate than /ask.
                identity = self._identity()
                if require_auth and identity is None:
                    self._send_json(401, {"error": "sign in with GitHub to continue"})
                    return
                try:
                    lib = registry.library_for(identity)
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                    return
                if not self._entitled(lib):
                    self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                    return
                # Straight from memory -- no writer call, and no re-reading
                # chunks.jsonl (~50k lines on a large repo).
                self._send_json(200, build_map(lib.current_pipeline().indexed_chunks(),
                                               lib.status_snapshot()))
            elif route == "/onboarding":
                # The tour PLAN: a constant, no writer and no retrieval, so a
                # client can render the whole shape instantly and then fetch
                # steps one at a time. Same entitlement gate as /map -- it
                # names the repo and its steps describe the caller's code.
                identity = self._identity()
                if require_auth and identity is None:
                    self._send_json(401, {"error": "sign in with GitHub to continue"})
                    return
                try:
                    lib = registry.library_for(identity)
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                    return
                if not self._entitled(lib):
                    self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                    return
                self._send_json(200, onboarding.plan(lib.status_snapshot()))
            elif route == "/auth/github/callback":
                self._github_callback()
            else:
                self._send_json(404, {"error": "not found"})

        def _github_callback(self):
            """GitHub's redirect lands here (inside the app's auth sheet, or the
            extension's launchWebAuthFlow tab). Exchange the code, then 302 to
            the login surface's own callback target so it closes/completes."""
            if oauth is None or not oauth.configured:
                self._send(503, b"GitHub login is not configured.", "text/plain; charset=utf-8")
                return
            q = parse_qs(urlparse(self.path).query)
            code = (q.get("code") or [""])[0]
            state = (q.get("state") or [""])[0]
            try:
                session_id, mode, redirect_target = oauth.complete(state, code)
            except Exception as e:
                # Surface the cause in the server log (safe: GitHub's error string
                # or "unknown/expired state" — never the code or client secret) so a
                # failed sign-in is diagnosable instead of a silent generic message.
                print(f"github callback failed: {e!r}", file=sys.stderr, flush=True)
                self._send(400, b"Sign-in failed or expired. Close this window and try again.",
                           "text/html; charset=utf-8")
                return
            # Web logins return to the same-origin page; the Mac app keeps its
            # icarus:// custom scheme (which closes its auth sheet); the browser
            # extension's chrome.identity.launchWebAuthFlow is watching for a
            # navigation to ITS OWN validated chromiumapp.org redirect_target
            # (oauth.begin already refused any other value for this mode — see
            # github_oauth.py's _CHROMIUMAPP_REDIRECT). The token is NOT in the
            # URL for any mode — only the single-use session id is.
            if mode == "web":
                location = f"/?session={session_id}"
            elif mode == "extension":
                location = f"{redirect_target}?session={session_id}"
            else:
                location = f"icarus://auth?session={session_id}"
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            # Validate the declared body length BEFORE routing or reading it, so a
            # negative/non-integer/oversized Content-Length is a clean 413 and
            # never a blocking read that holds a thread (M1).
            try:
                self._content_length()
            except ValueError:
                self._send_json(413, {"error": "request too large or malformed"})
                return
            # Auth endpoints must be reachable WITHOUT a token (you POST here to get one).
            if self.path == "/auth/github/begin":
                if oauth is None or not oauth.configured:
                    self._send_json(503, {"error": "github login not configured"})
                    return
                try:
                    body = self._body() or {}
                except (ValueError, AttributeError):
                    body = {}
                mode = body.get("mode", "app")
                # "app-private" is the same native flow as "app" -- same
                # icarus:// callback -- differing only in the scope it asks
                # GitHub for. An unknown value falls back to the LEAST
                # privileged mode, never the most.
                if mode not in ("app", "web", "extension", "app-private"):
                    mode = "app"
                redirect_target = body.get("redirect_target") if mode == "extension" else None
                try:
                    _, url = oauth.begin(mode, redirect_target=redirect_target)
                except ValueError as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"authorize_url": url})
                return
            if self.path == "/auth/github/redeem":
                if oauth is None:
                    self._send_json(503, {"error": "github login not configured"})
                    return
                try:
                    session = self._body().get("session")
                except (ValueError, AttributeError):
                    self._send_json(400, {"error": "missing session"})
                    return
                token = oauth.redeem(session) if session else None
                if not token:
                    self._send_json(404, {"error": "unknown or used session"})
                    return
                self._send_json(200, {"token": token})
                return
            if self.path == "/auth/agent/session":
                identity, kind, _grant = self._principal()
                if identity is None:
                    self._send_json(401, {"error": "sign in with GitHub to continue"})
                    return
                if kind != "github":
                    self._send_json(403, {"error": "a GitHub credential is required"})
                    return
                if agent_sessions is None or agent_repo_info is None:
                    self._send_json(404, {"error": "not found"})
                    return
                if not agent_session_limiter.allow(identity):
                    self._send_json(429, {"error": "slow down -- try again in a minute"})
                    return
                try:
                    lib = registry.library_for(identity)
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                    return
                snapshot = lib.status_snapshot() or {}
                repo = snapshot.get("repo")
                if not isinstance(repo, str) or not repo:
                    self._send_json(403, {"error": "agent sessions require an active repo"})
                    return
                # Private repos are allowed here since 2026-08-07 (see
                # docs/decisions/2026-08-07-mcp-private-repository-access.md).
                # The caller's own read access is still what gates this: the
                # session is minted against the repo THIS identity already
                # connected, and `_entitled` re-checks per request. What was
                # dropped is the public-only requirement, not authorization.
                try:
                    info = agent_repo_info(repo, self._github_token())
                except Exception:  # fail closed when GitHub cannot verify access
                    info = None
                if not isinstance(info, dict):
                    self._send_json(403, {"error": "GitHub could not verify access to the active repo"})
                    return
                token, expires_at = agent_sessions.issue(identity, repo)
                self._send_json(
                    200,
                    {"token": token, "expires_at": expires_at, "repo": repo},
                    headers={"Cache-Control": "no-store"},
                )
                return
            identity = self._identity()
            if identity is None:
                self._send_json(401, {"error": "sign in with GitHub to continue"})
                return
            if self._principal()[1] == "agent" and self.path not in ("/ask", "/explain", "/context"):
                self._send_json(403, {"error": "agent sessions are read-only and route-scoped"})
                return
            if self.path == "/disconnect":
                try:
                    # Read the repo BEFORE the disconnect, then forget any
                    # conversation about it: a subject must not outlive the
                    # caller's access to the thing it names. Best-effort, and
                    # ahead of the delete, so a store failure cannot leave the
                    # caller's on-disk data undeleted.
                    if conversations is not None:
                        try:
                            conversations.forget(
                                identity, registry.library_for(identity).provenance()[0])
                        except Exception as e:
                            print(f"conversation forget failed: {type(e).__name__}: {e}",
                                  file=sys.stderr)
                    registry.disconnect(identity)
                    self._send_json(200, registry.library_for(identity).status_snapshot())
                except _RegistryWarming:
                    self._send_json(503, {"error": "starting up, try again shortly"})
                except Exception as e:
                    # Deletion can genuinely fail (permissions, a file still in
                    # use). The registry already forgets this identity's
                    # in-memory state before attempting the on-disk delete (see
                    # demo/registry.py), so the failure must be surfaced
                    # honestly here instead of letting the exception drop the
                    # connection with no response -- never imply success on a
                    # failed delete.
                    print(f"/disconnect failed: {type(e).__name__}: {e}", file=sys.stderr)
                    self._send_json(500, {"error": "couldn't fully remove your data -- some files may remain, try again"})
                return
            try:
                lib = registry.library_for(identity)
            except _RegistryWarming:
                self._send_json(503, {"error": "starting up, try again shortly"})
                return
            if self.path == "/memory-gaps/record":
                if memory_writer is None or ledger is None:
                    self._send_json(404, {"error": "not found"})
                    return
                if self._principal()[1] != "github":
                    self._send_json(403, {"error": "a GitHub credential is required"})
                    return
                if not self._entitled(lib):
                    self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                    return
                try:
                    body = self._body()
                    gap_id = body["gap_id"]
                    rationale = body["rationale"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "gap_id and rationale are required"})
                    return
                if not isinstance(gap_id, str) or not _GAP_ID_RE.fullmatch(gap_id):
                    self._send_json(400, {"error": "gap_id is invalid"})
                    return
                if not isinstance(rationale, str) or not rationale.strip() \
                        or len(rationale.strip()) > 8000:
                    self._send_json(400, {"error": "rationale is required and must be at most 8000 characters"})
                    return
                tradeoffs = body.get("tradeoffs", "")
                references = body.get("references", [])
                if not isinstance(tradeoffs, str) or len(tradeoffs.strip()) > 4000:
                    self._send_json(400, {"error": "tradeoffs must be text at most 4000 characters"})
                    return
                if not isinstance(references, list) or any(
                    not isinstance(item, str) or not item.strip() or len(item.strip()) > 500
                    for item in references
                ) or sum(len(item.strip()) for item in references) > 4000:
                    self._send_json(400, {"error": "references must be a short list of text values"})
                    return

                repo, _commit = lib.provenance()
                try:
                    gap = next((
                        item for item in ledger.gaps(repo, include_resolved=True)
                        if item.get("id") == gap_id
                    ), None)
                except Exception as error:
                    print(f"memory gap read failed: {type(error).__name__}: {error}",
                          file=sys.stderr)
                    self._send_json(503, {"error": "the engineering-memory record is unavailable"})
                    return
                if (
                    gap is not None
                    and gap.get("status") == "proposed"
                    and isinstance(gap.get("proposal"), dict)
                ):
                    self._send_json(
                        200, gap["proposal"],
                        headers={"Cache-Control": "no-store"},
                    )
                    return
                if not memory_limiter.allow(identity):
                    self._send_json(429, {"error": "too many memory proposals -- try again later"})
                    return
                if (
                    gap is None
                    or gap.get("status") != "open"
                    or gap.get("actionable") is not True
                ):
                    self._send_json(
                        409,
                        {"error": "this is not an open, actionable engineering-memory gap"},
                    )
                    return
                try:
                    result = memory_writer.record(
                        repo=repo,
                        token=self._github_token(),
                        gap_id=gap_id,
                        question=gap["question"],
                        rationale=rationale.strip(),
                        tradeoffs=tradeoffs.strip(),
                        references=[item.strip() for item in references],
                    )
                except MemoryWriteError as error:
                    payload = {"error": str(error)}
                    if error.recovery_url:
                        payload["recovery_url"] = error.recovery_url
                    self._send_json(error.status, payload)
                    return
                except Exception as error:
                    print(f"memory record write failed: {type(error).__name__}: {error}",
                          file=sys.stderr)
                    self._send_json(502, {"error": "GitHub could not create the memory proposal"})
                    return
                try:
                    ledger.record_proposal(
                        repo,
                        gap_id=gap_id,
                        question=gap["question"],
                        result=result,
                    )
                except Exception as error:
                    print(
                        f"memory proposal ledger write failed: "
                        f"{type(error).__name__}: {error}",
                        file=sys.stderr,
                    )
                    self._send_json(502, {
                        "error": (
                            "GitHub created the proposal, but Icarus could not "
                            "persist its proposed state"
                        ),
                        "recovery_url": result.get("pull_request_url"),
                    })
                    return
                self._send_json(201, result, headers={"Cache-Control": "no-store"})
            elif self.path == "/ask":
                # Rate-limit BEFORE parsing/validating the body: a caller must not
                # be able to dodge the limiter by sending bodies that fail cheap
                # validation, and this also saves us from ever reaching the real
                # (billed) writer call below.
                if not ask_limiter.allow(identity):
                    self._send_json(429, {"error": "slow down -- try again in a minute"})
                    return
                # Entitlement BEFORE the body is parsed and long before the
                # writer: a caller who may not read this repo must cost nothing
                # at the model provider.
                if not self._entitled(lib):
                    self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                    return
                try:
                    body = self._body()
                    question = body["question"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing question"})
                    return
                if not isinstance(question, str) or not question.strip():
                    self._send_json(400, {"error": "missing question"})
                    return
                include_evidence = body.get("include_evidence", False)
                if not isinstance(include_evidence, bool):
                    self._send_json(400, {"error": "include_evidence must be true or false"})
                    return
                per_claim = body.get("per_claim", False)
                if not isinstance(per_claim, bool):
                    self._send_json(400, {"error": "per_claim must be true or false"})
                    return
                snapshot = lib.snapshot()
                repo, commit = snapshot.repo, snapshot.commit
                try:
                    # The caller's own token, so an exact "#N" they named in a
                    # PRIVATE repo can be live-fetched AS THEM. Never stored --
                    # it is read from this request's header and passed straight
                    # through (see GatedPipeline.answer). Without it a private
                    # repo's live fetch fails safe to None, as it always did.
                    # Passed ONLY when asked for, so the default call is
                    # byte-identical: `per_claim` is a GatedPipeline capability
                    # and the base Pipeline interface (plus every stub) does not
                    # take it. Sending it always would break every non-gated
                    # pipeline with a TypeError.
                    extra = {"per_claim": True} if per_claim else {}
                    answer_started = time.monotonic()
                    result = snapshot.pipeline.answer(
                        question, token=self._github_token(), **extra)
                    answer_latency = time.monotonic() - answer_started
                    still_indexing = snapshot.indexing
                except Exception as e:
                    # The rented writer failed -- missing/invalid key, provider
                    # outage, or exhausted retries. Return an honest JSON error
                    # instead of letting the exception drop the connection with no
                    # response. Logged server-side (never swallowed silently).
                    print(f"/ask writer failed: {type(e).__name__}: {e}", file=sys.stderr)
                    self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                    return
                # PostHog AI Observability ($ai_generation): latency + model/
                # provider are metadata, sent regardless of the content-share
                # setting; the prompt/completion only when sharing is on --
                # same rule _capture_product_event applies to question_asked.
                # No token/cost counts: Provider.complete() returns a bare
                # string (evals/provider.py), so Gemini's usageMetadata is
                # discarded before it ever reaches here -- disclosed gap,
                # not faked.
                try:
                    identity_for_ai, _kind, _grant = self._principal()
                    provider = getattr(snapshot, "provider", None)
                    ai_properties = {
                        "$ai_model": getattr(provider, "model", None),
                        "$ai_provider": type(provider).__name__ if provider else None,
                        # NOT $ai_latency. This clock covers the whole of
                        # pipeline.answer() -- exact-ref GitHub fetches,
                        # retrieval, evidence assembly, the writer AND the
                        # honesty gate -- so publishing it as the model's own
                        # latency corrupts any provider/model comparison built
                        # on it. Named for what it measures; the provider call
                        # is not timed at its own boundary today (Provider
                        # .complete returns a bare string), so $ai_latency is
                        # omitted rather than faked, exactly as token counts are.
                        "icarus_answer_latency_seconds": answer_latency,
                        "$ai_http_status": 200,
                        "repo": repo,
                    }
                    if self._share_content():
                        ai_properties["$ai_input"] = question
                        ai_properties["$ai_output_choices"] = [
                            {"content": result.answer if result.verdict == "answer" else ""}
                        ]
                    posthog_capture.capture("$ai_generation", identity_for_ai, ai_properties)
                except Exception as e:
                    print(f"posthog $ai_generation capture failed: {type(e).__name__}: {e}", file=sys.stderr)
                if ledger is not None and not include_evidence:
                    # Recorded against the REPO, and deliberately WITHOUT the
                    # asking identity -- a map of what the organisation never
                    # wrote down, not a record of who asked what. Never allowed
                    # to fail the answer the caller actually asked for: the
                    # ledger is an asset, not a dependency (Ledger.record
                    # swallows its own I/O errors; this catches anything else,
                    # including a broken ledger object).
                    # Evidence-opt-in asks come from the coding-agent adapter;
                    # recording its automatic preflights would turn human
                    # documentation demand into machine-generated noise.
                    try:
                        ledger.record(repo, question=question,
                                      reason=result.abstention_reason,
                                      verdict=result.verdict, citations=result.citations)
                    except Exception as e:
                        print(f"ledger write failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(
                    200,
                    build_payload(
                        result,
                        repo,
                        commit,
                        indexing=still_indexing,
                        include_evidence=include_evidence,
                    ),
                    capture_extra={"question": question},
                )
            elif self.path == "/onboarding":
                self._handle_onboarding(lib, identity)
            elif self.path == "/briefing":
                self._handle_briefing(mutate=True)
            elif self.path == "/explain":
                self._handle_explain(lib, identity)
            elif self.path == "/investigate":
                self._handle_investigate(lib, identity)
            elif self.path == "/context":
                self._handle_context(lib, identity)
            elif self.path == "/connect":
                # Same reasoning as /ask: check the limiter first, before the body
                # is even parsed, so a rate-limited caller never reaches the real
                # GitHub `repo_info` call or a background clone/ingest.
                if not connect_limiter.allow(identity):
                    self._send_json(429, {"error": "slow down -- try again later"})
                    return
                # Read the body ONCE: it comes off the socket and a second
                # read blocks forever waiting for bytes that will never arrive.
                try:
                    body = self._body()
                    repo = body["repo"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing repo"})
                    return
                if not isinstance(repo, str) or not _REPO_RE.match(repo.strip()):
                    self._send_json(400, {"error": "repo must look like owner/name"})
                    return
                repo = repo.strip()
                # An explicit re-ingest of an already-cached repo. Rejected
                # unless it is a real boolean: "true"/1/"yes" must not quietly
                # become a refresh, because one spends minutes of CPU and
                # republishes a corpus other entitled readers are using.
                refresh = body.get("refresh", False)
                if not isinstance(refresh, bool):
                    self._send_json(400, {"error": "refresh must be true or false"})
                    return
                # Checked only once we know this really IS a refresh, so an
                # ordinary connect never spends the re-ingest budget -- and
                # before any GitHub call or ingest, like the connect limiter
                # above. A refresh costs minutes of CPU (283s measured on
                # production) and republishes a corpus concurrent readers are
                # using, so it gets its own, much tighter allowance.
                if refresh and not refresh_limiter.allow(identity):
                    self._send_json(429, {"error": "a refresh re-reads the whole "
                                                   "repository -- try again later"})
                    return
                token = self._github_token()
                private = False
                if require_auth:
                    # Caller-scoped check BEFORE any clone/ingest: can THIS token
                    # actually read THIS repo? None means refuse (fail safe). A
                    # PRIVATE repo the caller CAN read routes to their own isolated
                    # storage, cloned with their token, answered by the private-safe
                    # writer (the trust interlock enforces that at pipeline build).
                    info = github_access.repo_info(repo, token)
                    if info is None:
                        self._send_json(403, {"error": "that repo doesn't exist or your GitHub account can't read it"})
                        return
                    private = bool(info["private"])
                # Access logging is suppressed below; record arrival, never the token.
                print(f"connect received: repo={repo!r} private={private} "
                      f"refresh={refresh} "
                      f"({'sync' if sync_connect else 'background'})", file=sys.stderr)
                if sync_connect:
                    # Background upgrade is safe only while Azure keeps a replica warm.
                    result = lib.connect_sync(
                        repo, token=(token if private else None), private=private,
                        background_upgrade=background_upgrade, refresh=refresh)
                    self._send_json(200, result)
                else:
                    # QUEUED: hand the ingest to a worker thread and answer now.
                    # Stage 1 (clone + the full PR/issue fetch + code walk +
                    # chunking) runs for minutes on a large repo, and a
                    # request-bound ingest is killed by Azure's fixed 240s
                    # ingress timeout long before it finishes -- measured live
                    # on astral-sh/uv 2026-08-10, which never connected at all.
                    # The work itself is fine; only the request waiting on it
                    # was the problem.
                    #
                    # `background_upgrade` was previously dropped here, so a
                    # queued connect silently ran stage 2 INLINE while the sync
                    # path backgrounded it -- the two routes disagreed about
                    # when a repo becomes answerable. Passed now, so the queued
                    # path publishes lexical search as early as the sync one.
                    threading.Thread(
                        target=lib.connect_sync, args=(repo,),
                        kwargs={"token": token if private else None, "private": private,
                                "background_upgrade": background_upgrade,
                                "refresh": refresh},
                        daemon=True).start()
                    # `state` stays "indexing", NOT a new "queued" value: an
                    # installed Mac app decodes this field and an unknown state
                    # would break it. `connecting_to` is the additive part, and
                    # is what makes a running job distinguishable from none.
                    self._send_json(202, {"state": "indexing", "repo": repo,
                                          "connecting_to": repo})
            else:
                self._send_json(404, {"error": "not found"})

        def _handle_briefing(self, mutate):
            """GET -> what changed since this caller was last here.
            POST -> acknowledge it, moving the anchor to the current commit.

            GET is deliberately PURE. If reading consumed the briefing, a
            client that crashed mid-render would lose it permanently, and the
            one thing a returning-user feature must not do is silently swallow
            the thing it exists to show.

            Guarded by the same entitlement check as /map and /ledger: this
            names the caller's connected repo and its commits.
            """
            identity = self._identity()
            if require_auth and identity is None:
                self._send_json(401, {"error": "sign in with GitHub to continue"})
                return
            if visits is None:
                # A deployment that has not accepted the returning-user
                # decision stores nothing about anyone, and says so with a 404
                # rather than an empty briefing that implies a store exists.
                self._send_json(404, {"error": "not found"})
                return
            try:
                lib = registry.library_for(identity)
            except _RegistryWarming:
                self._send_json(503, {"error": "starting up, try again shortly"})
                return
            if not self._entitled(lib):
                self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                return
            repo, commit = lib.provenance()
            user = identity or "anon"

            # Never on the answering path, and never on this one either: a
            # broken store degrades to "first visit", it does not 500.
            try:
                last = visits.last_visit(user, repo)
            except Exception:  # noqa: BLE001
                last = None

            if mutate:
                try:
                    visits.record(user, repo, commit)
                except Exception:  # noqa: BLE001
                    pass  # an asset, not a dependency
                self._send_json(200, {"acknowledged": True, "repo": repo,
                                      "commit": commit})
                return

            since = None
            if last and last["commit"] and commit and last["commit"] != commit:
                try:
                    since = commits_since(repo, last["commit"], commit,
                                          self._github_token())
                except Exception:  # noqa: BLE001
                    since = None
            elif last and last["commit"] == commit:
                since = 0

            self._send_json(200, {
                "repo": repo,
                "first_visit": last is None,
                "last_visit_at": last["at"] if last else None,
                "last_seen_commit": last["commit"] if last else None,
                "current_commit": commit,
                # None means UNKNOWN, exactly as in /status's freshness block.
                # It must never be rendered as "nothing changed" -- a failed
                # lookup reading as "you're all caught up" is the same class
                # of failure as a bluffed citation.
                "commits_since": since,
                # Decision doc property 3, made literal: the caller can see
                # the WHOLE record held about them, which is this and nothing
                # else. A privacy promise nobody can verify is marketing.
                "stored": ({"repo": repo, "commit": last["commit"], "at": last["at"]}
                           if last else None),
            })

        def _handle_onboarding(self, lib, identity):
            """POST /onboarding {"step": "purpose"} -> one cited tour step.

            Reuses `ask_limiter` -- a tour step reaches the same billed writer
            as /ask -- and the same read-entitlement check, since it reads the
            same corpus. Returns the IDENTICAL `build_payload` shape as /ask
            plus the step id and title, so every client renders the tour with
            the renderer it already has.

            Deliberately NOT recorded in the ask ledger. The ledger ranks gaps
            by how OFTEN a question was asked, and machine-generated steps
            fired once per connect per user would swamp the questions a team
            actually asked -- inventing documentation debt nobody was looking
            for. The tour reads the corpus; it does not speak for the team.
            """
            if not ask_limiter.allow(identity):
                self._send_json(429, {"error": "slow down -- try again in a minute"})
                return
            if not self._entitled(lib):
                self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                return
            try:
                step = self._body()["step"]
            except (ValueError, KeyError, TypeError):
                self._send_json(400, {"error": "missing step"})
                return
            if not isinstance(step, str) or not step.strip():
                self._send_json(400, {"error": "missing step"})
                return
            repo, commit = lib.provenance()
            try:
                result = onboarding.answer_step(
                    lib.current_pipeline(), lib.status_snapshot(), step.strip(),
                    token=self._github_token())
            except ValueError:
                # An unknown step id -- including one measurement CUT from the
                # tour -- is a caller error, never a silently-invented question.
                self._send_json(400, {"error": "unknown onboarding step"})
                return
            except Exception as e:
                print(f"/onboarding writer failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                return
            payload = build_payload(result, repo, commit,
                                    indexing=bool(lib.status_snapshot().get("indexing")))
            payload["step"] = step.strip()
            payload["title"] = onboarding.title_for(step.strip())
            self._send_json(200, payload)

        def _handle_explain(self, lib, identity):
            """Brick D: POST /explain {repo, path, start, end[, question]} -> a
            cited answer or honest unknown for a GitHub line selection.

            Reuses `ask_limiter` -- /explain reaches the same billed writer as
            /ask, so it shares that budget rather than getting its own. `repo`
            must match the caller's CURRENTLY connected repo (refuses, never
            silently answers about a repo the caller isn't connected to, and
            never switches repos as a side effect of asking).

            Guarded by the same read-entitlement check as /ask -- it reads the
            same corpus, so protecting /ask alone would leave a side door open."""
            if not ask_limiter.allow(identity):
                self._send_json(429, {"error": "slow down -- try again in a minute"})
                return
            if not self._entitled(lib):
                self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                return
            try:
                body = self._body()
                repo = body["repo"]
                path = body["path"]
                start = body["start"]
                end = body["end"]
            except (ValueError, KeyError, TypeError):
                self._send_json(400, {"error": "missing repo/path/start/end"})
                return
            if not isinstance(repo, str) or not repo.strip():
                self._send_json(400, {"error": "missing repo"})
                return
            if not isinstance(path, str) or not path.strip():
                self._send_json(400, {"error": "missing path"})
                return
            # bool is an int subclass in Python; explicitly excluded so a
            # stray true/false body value fails validation rather than being
            # silently coerced into 0/1.
            if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) \
                    or not isinstance(end, int) or start < 1 or end < start:
                self._send_json(400, {"error": "start/end must be positive integers with end >= start"})
                return
            question = body.get("question")
            if question is not None:
                if not isinstance(question, str):
                    self._send_json(400, {"error": "question must be a string"})
                    return
                question = question.strip()
            include_evidence = body.get("include_evidence", False)
            if not isinstance(include_evidence, bool):
                self._send_json(400, {"error": "include_evidence must be true or false"})
                return
            per_claim = body.get("per_claim", False)
            if not isinstance(per_claim, bool):
                self._send_json(400, {"error": "per_claim must be true or false"})
                return
            snapshot = lib.snapshot()
            active_repo, commit = snapshot.repo, snapshot.commit
            if repo.strip() != active_repo:
                self._send_json(409, {"error": "that repo isn't your currently connected repo"})
                return
            try:
                extra = {"per_claim": True} if per_claim else {}
                result = snapshot.pipeline.explain(
                    path.strip(), start, end, question=question, **extra)
                still_indexing = snapshot.indexing
            except Exception as e:
                print(f"/explain writer failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                return
            self._send_json(
                200,
                build_payload(
                    result,
                    active_repo,
                    commit,
                    indexing=still_indexing,
                    include_evidence=include_evidence,
                ),
                capture_extra={"question": question or f"{path.strip()}#L{start}-{end}"},
            )

        def _handle_investigate(self, lib, identity):
            """POST /investigate {question} -> a cited conclusion, its findings
            with their support classes, and the trail that produced them.

            Has its OWN rate limiter (production default 3/min), not `/ask`'s:
            one investigation makes several billed writer calls where an ask
            makes one, so sharing a per-request allowance would let a caller
            spend roughly ten times the budget `/ask` bounds. Entitlement is the
            same check `/ask` applies, and both are checked before any provider
            call.

            Conversational continuity is opt-in per request in the sense that it
            requires an identity: an unauthenticated local caller gets a
            perfectly good standalone investigation, exactly as `/ask` behaves
            today. Nothing degrades without it.
            """
            # Checked BEFORE the body is parsed and long before any provider
            # call, so a refused caller costs nothing at the model provider.
            if not investigate_limiter.allow(identity):
                self._send_json(429, {"error": "an investigation makes several model "
                                               "calls -- try again in a minute"})
                return
            if not self._entitled(lib):
                self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                return
            try:
                body = self._body()
                question = body["question"]
            except (ValueError, KeyError, TypeError):
                self._send_json(400, {"error": "missing question"})
                return
            if not isinstance(question, str) or not question.strip():
                self._send_json(400, {"error": "missing question"})
                return
            question = question.strip()
            # A caller can start a fresh enquiry without waiting for the old one
            # to expire -- "forget what we were talking about". Rejected unless
            # it is a real boolean, like /connect's refresh flag.
            fresh = body.get("fresh", False)
            if not isinstance(fresh, bool):
                self._send_json(400, {"error": "fresh must be true or false"})
                return
            # ONE atomic view of the corpus for the whole request. Reading
            # provenance and the pipeline separately let a concurrent refresh
            # tear them apart: answering from one index while returning citation
            # URLs and conversation provenance from another.
            snapshot = lib.snapshot()
            corpus = snapshot.corpus_id
            repo, commit = snapshot.repo, snapshot.commit

            # -- inherit the subject, deterministically -----------------------
            # Only when the question names no refs of its own AND uses a
            # referring word. A model is never asked what "it" means: a wrongly
            # inherited subject yields a confident, fully-cited answer about the
            # wrong change, which the honesty gate cannot detect (groundedness
            # proves a citation is real, never that it is relevant -- the
            # 2026-08-06 selection-drift finding).
            # The request sequence this run owns. Every request advances it, so
            # an older overlapping follow-up cannot finish later and overwrite
            # the newer conversation state.
            generation = conversations.begin(identity, repo, fresh) if conversations else None
            # Resumed at THIS commit: a refresh republishes the corpus, and
            # findings verified against the old index must not be carried into
            # an answer about the new one.
            prior = None if fresh else (
                conversations.resume(identity, repo, corpus) if conversations else None)
            subject = objective = None
            carried = None
            if prior is not None and refers_back(question) \
                    and not _investigator._anchor_refs(question, snapshot.pipeline):
                subject, objective = list(prior.subject), prior.objective
                # Findings from earlier turns, so this one compounds rather than
                # re-deriving what the conversation already established.
                carried = prior.claims

            try:
                # The diff fetcher is bound to the ACTIVE repo here rather than
                # inside the pipeline: it is the only probe that reaches GitHub
                # for something never indexed, and binding it per request keeps
                # the caller's token out of any longer-lived object.
                diff_fetch = (lambda number, tok=None:
                              fetch_pr_diff(repo, number, token=tok)) if repo else None
                # Filled BY the investigation, not rebuilt from the index
                # afterwards: rebuilding loses every live-fetched piece of
                # evidence (an unindexed pull request, a commit, a diff), which
                # blanks its excerpt and leaves the gate checking empty text.
                texts = {}
                investigation = _investigator.investigate(
                    question, snapshot.pipeline, entity_index(lib, snapshot),
                    snapshot.provider, token=self._github_token(),
                    subject=subject, objective=objective, carried=carried,
                    diff_fetch=diff_fetch, texts=texts)
                result = _investigator.conclude(
                    investigation, snapshot.provider, texts=texts)
                still_indexing = snapshot.indexing
            except Exception as e:
                print(f"/investigate failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                return

            if conversations is not None:
                # Continuity is an improvement on a stateless answer, never a
                # precondition for one: a store failure must not cost the caller
                # the answer they already paid the writer for.
                try:
                    conversations.remember(identity, repo, investigation,
                                           commit=corpus, generation=generation,
                                           is_indexed=lambda ref: snapshot.pipeline.chunk_for(ref)
                                           is not None)
                except Exception as e:
                    print(f"conversation write failed: {type(e).__name__}: {e}",
                          file=sys.stderr)
            if ledger is not None:
                # Recorded exactly as /ask records an ask -- against the repo,
                # never the asker. An investigation that honestly abstains is
                # documentation debt in the same way an ask is, and excluding it
                # would under-report what the team never wrote down.
                try:
                    ledger.record(repo, question=question,
                                  reason=result.abstention_reason,
                                  verdict=result.verdict, citations=result.citations)
                except Exception as e:
                    print(f"ledger write failed: {type(e).__name__}: {e}", file=sys.stderr)
            self._send_json(200, build_investigation_payload(
                result, investigation, repo, commit, indexing=still_indexing),
                capture_extra={"question": question})

        def _handle_context(self, lib, identity):
            """POST /context {task} -> structured pre-implementation context:
            architecture, dependencies, files touched, decisions (with support
            class), PRs/issues gathered, RISKS (pull requests already tried and
            refused -- evals/attempts.py), disclosed constraints, unknowns, and
            the citations the answer actually rests on. NOT a conversational
            answer -- Experiment B's `icarus.context(task)` (docs/HANDOFF.md).

            Reuses the exact `/investigate` engine -- same investigate()/
            conclude() call, same honesty gate, same entitlement check, same
            rate budget (`investigate_limiter`: an investigation spends several
            billed writer calls, same as /investigate). This endpoint adds NO
            new retrieval and NO new model call; it only reshapes an
            investigation's already-gated output (evals/context_package) and
            adds demo/structure.py's already-deterministic dependency map.

            Deliberately STATELESS, unlike /investigate: no conversation
            continuity, no `fresh` flag, no subject inheritance. A caller
            asking "what do I need to know before doing X" is not a follow-up
            question about a prior "it" -- keeping this smaller than
            /investigate is the point (see the module's own "do not
            over-engineer" brief).
            """
            if not investigate_limiter.allow(identity):
                self._send_json(429, {"error": "an investigation makes several model "
                                               "calls -- try again in a minute"})
                return
            if not self._entitled(lib):
                self._send_json(403, {"error": "your GitHub account can't read the connected repo"})
                return
            try:
                body = self._body()
                task = body["task"]
            except (ValueError, KeyError, TypeError):
                self._send_json(400, {"error": "missing task"})
                return
            if not isinstance(task, str) or not task.strip():
                self._send_json(400, {"error": "missing task"})
                return
            task = task.strip()
            snapshot = lib.snapshot()
            repo, commit = snapshot.repo, snapshot.commit
            try:
                diff_fetch = (lambda number, tok=None:
                              fetch_pr_diff(repo, number, token=tok)) if repo else None
                texts = {}
                investigation = _investigator.investigate(
                    task, snapshot.pipeline, entity_index(lib, snapshot),
                    snapshot.provider, token=self._github_token(), diff_fetch=diff_fetch,
                    texts=texts)
                result = _investigator.conclude(
                    investigation, snapshot.provider, texts=texts)
                structure = build_structure(snapshot.pipeline.indexed_chunks())
                package = build_context_package(investigation, result, structure, texts)
                still_indexing = snapshot.indexing
            except Exception as e:
                print(f"/context failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                return
            self._send_json(200, build_context_payload(
                package, repo, commit, indexing=still_indexing))

    return Handler


def resolve_provenance(meta_path, questions_path):
    """Default repo/commit for the committed corpus: prefer its meta.json, else
    fall back to the labelled set's corpus block."""
    meta = load_meta(meta_path)
    if meta:
        return meta["repo"], meta["commit"]
    corpus = json.loads(Path(questions_path).read_text())["corpus"]
    return corpus["repo"], corpus["commit"]


def serve(host: str = None, port: int = None):
    load_env_file(REPO_ROOT / ".env")  # pick up keys from a gitignored .env
    if not os.environ.get("GEMINI_PAID_API_KEY"):
        print("WARNING: GEMINI_PAID_API_KEY is not set -- it is the alpha's writer; "
              "/ask and /explain will return "
              "503 until it is configured.", file=sys.stderr)
    # Bind from env so a PaaS (e.g. Render injects $PORT) can place us; loopback
    # defaults keep local dev unchanged.
    host = host if host is not None else os.environ.get("HOST", "127.0.0.1")
    port = int(port) if port is not None else int(os.environ.get("PORT", "8000"))
    default_repo, commit = resolve_provenance(CORPUS_META, QUESTIONS)
    storage_root = _resolve_storage_root(os.environ.get("ICARUS_STORAGE_ROOT"), REPO_ROOT / "data")
    registry = _LazyRegistry(lambda: LibraryRegistry(CORPUS_DIR, storage_root, default_repo))
    require_auth = bool(os.environ.get("ICARUS_REQUIRE_GITHUB_AUTH"))
    verifier = GitHubTokenVerifier() if require_auth else None
    agent_sessions = AgentSessionStore() if require_auth else None
    # Read entitlement for a shared per-repo index. Only meaningful with auth on
    # (without it there is a single local operator and no tenancy to enforce).
    access_verifier = RepoAccessVerifier() if require_auth else None
    # The shared ask ledger. A sibling of the corpus caches, never inside one --
    # ingest publishes a corpus with os.replace(), which would take the team's
    # whole question history with it on the next re-index. The '.' matches the
    # cache roots' convention: `registry._key` forbids '.', so no user id can
    # ever collide with or reach into it.
    ledger = Ledger(storage_root / "ask.ledger")
    allowed_hosts = _parse_allowed_hosts(os.environ.get("ICARUS_ALLOWED_HOSTS"))
    # OAuth callback: a public HTTPS URL when hosted (ICARUS_PUBLIC_URL), else the
    # loopback callback for local dev. GitHub must have this exact URL registered.
    public_url = os.environ.get("ICARUS_PUBLIC_URL")
    callback_base = public_url.rstrip("/") if public_url else f"http://{host}:{port}"
    # Web GitHub login: enabled only when the client id + secret are configured.
    oauth = None
    cid, secret = os.environ.get("GITHUB_CLIENT_ID"), os.environ.get("GITHUB_CLIENT_SECRET")
    if cid and secret:
        oauth = github_oauth.OAuthFlow(cid, secret, f"{callback_base}/auth/github/callback")
    sync_connect = bool(os.environ.get("ICARUS_SYNC_CONNECT"))
    # Option B: on a warm-replica request-scoped-CPU host, block /connect only
    # through STAGE 1 and embed in the background (see make_handler's use). Only
    # meaningful together with sync_connect.
    background_upgrade = bool(os.environ.get("ICARUS_BACKGROUND_UPGRADE"))
    handler = make_handler(registry, str(INDEX_HTML), require_auth=require_auth,
                           verifier=verifier, oauth=oauth, allowed_hosts=allowed_hosts,
                           sync_connect=sync_connect, background_upgrade=background_upgrade,
                           access_verifier=access_verifier, default_repo=default_repo,
                           ledger=ledger, freshness=FreshnessChecker(),
                           agent_sessions=agent_sessions,
                           agent_repo_info=github_access.repo_info,
                           memory_writer=GitHubMemoryWriter(),
                           # Returning-user state lives under each caller's own
                           # storage dir -- the exact tree /disconnect deletes,
                           # so "deletable, and actually deleted" needs no
                           # second mechanism. See
                           # docs/decisions/2026-07-30-returning-user-state.md.
                           visits=VisitStore(storage_root))
    httpd = ThreadingHTTPServer((host, port), handler)
    if allowed_hosts and "*" in allowed_hosts:
        host_note = "any host (cloud: relies on the bearer gate)"
    elif allowed_hosts:
        host_note = "hosts: " + ",".join(sorted(allowed_hosts))
    else:
        host_note = "loopback only"
    auth_note = "GitHub bearer required" if require_auth else "open (loopback only)"
    login_note = "web login on" if oauth else "web login off (set GITHUB_CLIENT_ID/SECRET)"
    if sync_connect:
        connect_note = ("sync connect: stage-1 block + background embed (Option B)"
                        if background_upgrade else "sync connect: blocks through embed")
    else:
        connect_note = "background connect"
    print(f"Icarus demo on http://{host}:{port}  (corpus: {default_repo} @ {commit[:12]}; "
          f"{host_note}; auth: {auth_note}; {login_note}; {connect_note})")
    print("Type any public owner/repo in the app to switch. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve()
