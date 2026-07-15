# demo/server.py
"""A minimal local web face over the gated brain. Stdlib http.server only.

GET  /        -> the static demo page (demo/index.html)
GET  /health  -> {"ok": true, "repo": ..., "commit": ...} -- liveness + provenance
GET  /status  -> the active repo + switch status (JSON)
POST /ask     -> {"question": "..."} -> the build_payload JSON for the page
POST /connect -> {"repo": "owner/name"} -> start indexing/switching to that repo
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from evals.corpus_meta import load_meta
from evals.env_file import load_env_file

from .payload import build_payload
from .registry import LibraryRegistry
from .auth import bearer_token, GitHubTokenVerifier
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
                 sync_connect: bool = False, background_upgrade: bool = False):
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
    """
    hosts = set(allowed_hosts) if allowed_hosts is not None else set(_LOOPBACK_HOSTS)
    wildcard = "*" in hosts
    ask_limiter = ask_limiter or RateLimiter(30, 60)          # 30 asks/min
    connect_limiter = connect_limiter or RateLimiter(5, 600)  # 5 connects/10min

    class Handler(BaseHTTPRequestHandler):
        _MAX_BODY = 64 * 1024
        # Per-connection socket timeout (defense in depth for M1): a client that
        # opens a connection and then dribbles or stalls its body can't hold a
        # server thread open indefinitely -- a blocking recv past this is cut.
        # Well above any legitimate 64KB body upload; only bites a stalled client.
        timeout = 60

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, code, body: bytes, content_type: str):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code, obj):
            self._send(code, json.dumps(obj).encode(), "application/json")

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

        def do_GET(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            route = urlparse(self.path).path
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
                self._send_json(200, lib.status_snapshot())
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
                if mode not in ("app", "web", "extension"):
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
            identity = self._identity()
            if identity is None:
                self._send_json(401, {"error": "sign in with GitHub to continue"})
                return
            if self.path == "/disconnect":
                try:
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
            if self.path == "/ask":
                # Rate-limit BEFORE parsing/validating the body: a caller must not
                # be able to dodge the limiter by sending bodies that fail cheap
                # validation, and this also saves us from ever reaching the real
                # (billed) writer call below.
                if not ask_limiter.allow(identity):
                    self._send_json(429, {"error": "slow down -- try again in a minute"})
                    return
                try:
                    question = self._body()["question"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing question"})
                    return
                if not isinstance(question, str) or not question.strip():
                    self._send_json(400, {"error": "missing question"})
                    return
                repo, commit = lib.provenance()
                try:
                    result = lib.current_pipeline().answer(question)
                except Exception as e:
                    # The rented writer failed -- missing/invalid key, provider
                    # outage, or exhausted retries. Return an honest JSON error
                    # instead of letting the exception drop the connection with no
                    # response. Logged server-side (never swallowed silently).
                    print(f"/ask writer failed: {type(e).__name__}: {e}", file=sys.stderr)
                    self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                    return
                self._send_json(200, build_payload(result, repo, commit))
            elif self.path == "/explain":
                self._handle_explain(lib, identity)
            elif self.path == "/connect":
                # Same reasoning as /ask: check the limiter first, before the body
                # is even parsed, so a rate-limited caller never reaches the real
                # GitHub `repo_info` call or a background clone/ingest.
                if not connect_limiter.allow(identity):
                    self._send_json(429, {"error": "slow down -- try again later"})
                    return
                try:
                    repo = self._body()["repo"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing repo"})
                    return
                if not isinstance(repo, str) or not _REPO_RE.match(repo.strip()):
                    self._send_json(400, {"error": "repo must look like owner/name"})
                    return
                repo = repo.strip()
                token = bearer_token(self.headers)
                if require_auth:
                    # Caller-scoped check BEFORE any clone/ingest: can THIS token
                    # actually read THIS repo? None means refuse (fail safe).
                    info = github_access.repo_info(repo, token)
                    if info is None:
                        self._send_json(403, {"error": "that repo doesn't exist or your GitHub account can't read it"})
                        return
                    if info["private"]:
                        self._send_json(403, {"error": "private repos are not available in this alpha"})
                        return
                # Access logging is suppressed below; record arrival, never token.
                print(f"connect received: repo={repo!r} "
                      f"({'sync' if sync_connect else 'background'})", file=sys.stderr)
                if sync_connect:
                    # Background upgrade is safe only while Azure keeps a replica warm.
                    result = lib.connect_sync(repo, background_upgrade=background_upgrade)
                    self._send_json(200, result)
                else:
                    threading.Thread(target=lib.connect_sync, args=(repo,), daemon=True).start()
                    self._send_json(202, {"state": "indexing", "repo": repo})
            else:
                self._send_json(404, {"error": "not found"})

        def _handle_explain(self, lib, identity):
            """Brick D: POST /explain {repo, path, start, end[, question]} -> a
            cited answer or honest unknown for a GitHub line selection.

            Reuses `ask_limiter` -- /explain reaches the same billed writer as
            /ask, so it shares that budget rather than getting its own. `repo`
            must match the caller's CURRENTLY connected repo (refuses, never
            silently answers about a repo the caller isn't connected to, and
            never switches repos as a side effect of asking)."""
            if not ask_limiter.allow(identity):
                self._send_json(429, {"error": "slow down -- try again in a minute"})
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
                question = question.strip() or None
            active_repo, commit = lib.provenance()
            if repo.strip() != active_repo:
                self._send_json(409, {"error": "that repo isn't your currently connected repo"})
                return
            try:
                result = lib.current_pipeline().explain(path.strip(), start, end, question=question)
            except Exception as e:
                print(f"/explain writer failed: {type(e).__name__}: {e}", file=sys.stderr)
                self._send_json(503, {"error": "the answering model is unavailable right now -- try again shortly"})
                return
            self._send_json(200, build_payload(result, active_repo, commit))

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
                           sync_connect=sync_connect, background_upgrade=background_upgrade)
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
