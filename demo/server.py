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
Public repos only on free hosted models. Run: GROQ_API_KEY=... python3 -m demo.server
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


def _resolve_storage_root(raw, default):
    """ICARUS_STORAGE_ROOT, falling back to `default` when unset OR set-but-
    blank (a PaaS env-var UI can easily leave a value blank rather than unset;
    `os.environ.get(key, default)` alone would silently resolve that to the
    cwd instead of the intended default)."""
    return Path(raw or default)


def make_handler(registry, html_path: str, require_auth: bool = False, verifier=None,
                 oauth=None, allowed_hosts=None, ask_limiter=None, connect_limiter=None):
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
    """
    hosts = set(allowed_hosts) if allowed_hosts is not None else set(_LOOPBACK_HOSTS)
    wildcard = "*" in hosts
    ask_limiter = ask_limiter or RateLimiter(30, 60)          # 30 asks/min
    connect_limiter = connect_limiter or RateLimiter(5, 600)  # 5 connects/10min

    class Handler(BaseHTTPRequestHandler):
        _MAX_BODY = 64 * 1024

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

        def _body(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > self._MAX_BODY:
                raise ValueError("body too large")
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
                lib = registry.library_for(self._identity())
                repo, commit = lib.provenance()
                self._send_json(200, {"ok": True, "repo": repo, "commit": commit})
            elif route == "/status":
                lib = registry.library_for(self._identity())
                self._send_json(200, lib.status_snapshot())
            elif route == "/auth/github/callback":
                self._github_callback()
            else:
                self._send_json(404, {"error": "not found"})

        def _github_callback(self):
            """GitHub's redirect lands here (inside the app's auth sheet). Exchange
            the code, then 302 to the app's `icarus://` scheme so the sheet closes."""
            if oauth is None or not oauth.configured:
                self._send(503, b"GitHub login is not configured.", "text/plain; charset=utf-8")
                return
            q = parse_qs(urlparse(self.path).query)
            code = (q.get("code") or [""])[0]
            state = (q.get("state") or [""])[0]
            try:
                session_id, mode = oauth.complete(state, code)
            except Exception as e:
                # Surface the cause in the server log (safe: GitHub's error string
                # or "unknown/expired state" — never the code or client secret) so a
                # failed sign-in is diagnosable instead of a silent generic message.
                print(f"github callback failed: {e!r}", file=sys.stderr, flush=True)
                self._send(400, b"Sign-in failed or expired. Close this window and try again.",
                           "text/html; charset=utf-8")
                return
            # Web logins return to the same-origin page; the Mac app keeps its
            # icarus:// custom scheme (which closes its auth sheet). The token is
            # NOT in the URL — only the single-use session id is.
            location = f"/?session={session_id}" if mode == "web" else f"icarus://auth?session={session_id}"
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > self._MAX_BODY:
                self._send_json(413, {"error": "request too large"})
                return
            # Auth endpoints must be reachable WITHOUT a token (you POST here to get one).
            if self.path == "/auth/github/begin":
                if oauth is None or not oauth.configured:
                    self._send_json(503, {"error": "github login not configured"})
                    return
                try:
                    mode = (self._body() or {}).get("mode", "app")
                except (ValueError, AttributeError):
                    mode = "app"
                if mode not in ("app", "web"):
                    mode = "app"
                _, url = oauth.begin(mode)
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
                registry.disconnect(identity)
                self._send_json(200, registry.library_for(identity).status_snapshot())
                return
            lib = registry.library_for(identity)
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
                payload = build_payload(lib.current_pipeline().answer(question), repo, commit)
                self._send_json(200, payload)
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
                private = False
                if require_auth:
                    # Caller-scoped check BEFORE any clone/ingest: can THIS token
                    # actually read THIS repo? None means refuse (fail safe).
                    info = github_access.repo_info(repo, token)
                    if info is None:
                        self._send_json(403, {"error": "that repo doesn't exist or your GitHub account can't read it"})
                        return
                    private = info["private"]
                threading.Thread(target=lib.connect_sync, args=(repo,),
                                 kwargs={"token": token if private else None, "private": private},
                                 daemon=True).start()
                self._send_json(202, {"state": "indexing", "repo": repo})
            else:
                self._send_json(404, {"error": "not found"})

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
    # Bind from env so a PaaS (e.g. Render injects $PORT) can place us; loopback
    # defaults keep local dev unchanged.
    host = host if host is not None else os.environ.get("HOST", "127.0.0.1")
    port = int(port) if port is not None else int(os.environ.get("PORT", "8000"))
    default_repo, commit = resolve_provenance(CORPUS_META, QUESTIONS)
    storage_root = _resolve_storage_root(os.environ.get("ICARUS_STORAGE_ROOT"), REPO_ROOT / "data")
    registry = LibraryRegistry(CORPUS_DIR, storage_root, default_repo)
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
    handler = make_handler(registry, str(INDEX_HTML), require_auth=require_auth,
                           verifier=verifier, oauth=oauth, allowed_hosts=allowed_hosts)
    httpd = ThreadingHTTPServer((host, port), handler)
    if allowed_hosts and "*" in allowed_hosts:
        host_note = "any host (cloud: relies on the bearer gate)"
    elif allowed_hosts:
        host_note = "hosts: " + ",".join(sorted(allowed_hosts))
    else:
        host_note = "loopback only"
    auth_note = "GitHub bearer required" if require_auth else "open (loopback only)"
    login_note = "web login on" if oauth else "web login off (set GITHUB_CLIENT_ID/SECRET)"
    print(f"Icarus demo on http://{host}:{port}  (corpus: {default_repo} @ {commit[:12]}; "
          f"{host_note}; auth: {auth_note}; {login_note})")
    print("Type any public owner/repo in the app to switch. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve()
