# demo/server.py
"""A minimal local web face over the gated brain. Stdlib http.server only.

GET  /        -> the static demo page (demo/index.html)
GET  /health  -> {"ok": true, "repo": ..., "commit": ...} -- liveness + provenance
GET  /status  -> the active repo + switch status (JSON)
POST /ask     -> {"question": "..."} -> the build_payload JSON for the page
POST /connect -> {"repo": "owner/name"} -> start indexing/switching to that repo

The active pipeline lives in a Library (demo/library.py); the handler is a thin
shell over it. /connect runs in a background thread so the request returns
immediately and the page polls /status. No brain code changes -- packaging only.
Public repos only on free hosted models. Run: GROQ_API_KEY=... python3 -m demo.server
"""

import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from evals.corpus_meta import load_meta
from evals.env_file import load_env_file

from .payload import build_payload
from .library import Library
from .auth import bearer_token, GitHubTokenVerifier
from . import github_oauth

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
CORPUS_DIR = ROOT.parent / "evals" / "corpus"
CORPUS_META = CORPUS_DIR / "meta.json"
CACHE_ROOT = CORPUS_DIR / "cache"
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


def make_handler(library, html_path: str, require_auth: bool = False, verifier=None,
                 oauth=None, allowed_hosts=None):
    """Build a request handler bound to a Library (the active-repo state).

    `require_auth` gates /ask and /connect behind a valid GitHub bearer token
    (verified by `verifier`); the plain web demo leaves it False and relies on
    the loopback bind + Host/Origin guard. `oauth` (an OAuthFlow) enables the web
    GitHub login endpoints; None leaves them off. `allowed_hosts` overrides the
    loopback-only Host allow-list (a set); include '*' to accept any Host/Origin
    (cloud mode — the bearer gate becomes the real boundary). None = loopback only.
    """
    hosts = set(allowed_hosts) if allowed_hosts is not None else set(_LOOPBACK_HOSTS)
    wildcard = "*" in hosts

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

        def _authenticated(self) -> bool:
            """True if auth isn't required, or a valid GitHub bearer is present."""
            if not require_auth:
                return True
            token = bearer_token(self.headers)
            return bool(token) and verifier is not None and verifier.verify(token)

        def do_GET(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            route = urlparse(self.path).path
            if route == "/":
                self._send(200, Path(html_path).read_bytes(), "text/html; charset=utf-8")
            elif route == "/health":
                repo, commit = library.provenance()
                self._send_json(200, {"ok": True, "repo": repo, "commit": commit})
            elif route == "/status":
                self._send_json(200, library.status_snapshot())
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
                session_id = oauth.complete(state, code)
            except Exception:
                self._send(400, b"Sign-in failed or expired. Close this window and try again.",
                           "text/html; charset=utf-8")
                return
            self.send_response(302)
            self.send_header("Location", f"icarus://auth?session={session_id}")
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
                _, url = oauth.begin()
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
            if not self._authenticated():
                self._send_json(401, {"error": "sign in with GitHub to continue"})
                return
            if self.path == "/ask":
                try:
                    question = self._body()["question"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing question"})
                    return
                if not isinstance(question, str) or not question.strip():
                    self._send_json(400, {"error": "missing question"})
                    return
                repo, commit = library.provenance()
                payload = build_payload(library.current_pipeline().answer(question), repo, commit)
                self._send_json(200, payload)
            elif self.path == "/connect":
                try:
                    repo = self._body()["repo"]
                except (ValueError, KeyError, TypeError):
                    self._send_json(400, {"error": "missing repo"})
                    return
                if not isinstance(repo, str) or not _REPO_RE.match(repo.strip()):
                    self._send_json(400, {"error": "repo must look like owner/name"})
                    return
                threading.Thread(target=library.connect_sync, args=(repo.strip(),), daemon=True).start()
                self._send_json(202, {"state": "indexing", "repo": repo.strip()})
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
    library = Library(CORPUS_DIR, CACHE_ROOT, default_repo)
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
    handler = make_handler(library, str(INDEX_HTML), require_auth=require_auth,
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
