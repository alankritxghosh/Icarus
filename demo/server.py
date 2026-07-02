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
from urllib.parse import urlparse

from evals.corpus_meta import load_meta
from evals.env_file import load_env_file

from .payload import build_payload
from .library import Library
from .auth import bearer_token, GitHubTokenVerifier

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
CORPUS_DIR = ROOT.parent / "evals" / "corpus"
CORPUS_META = CORPUS_DIR / "meta.json"
CACHE_ROOT = CORPUS_DIR / "cache"
QUESTIONS = ROOT.parent / "evals" / "phase1_questions.json"
INDEX_HTML = ROOT / "index.html"

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def make_handler(library, html_path: str, require_auth: bool = False, verifier=None):
    """Build a request handler bound to a Library (the active-repo state).

    `require_auth` gates /ask and /connect behind a valid GitHub bearer token
    (verified by `verifier`); the plain web demo leaves it False and relies on
    the loopback bind + Host/Origin guard.
    """

    class Handler(BaseHTTPRequestHandler):
        _ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
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
            POST from a website (attacker's Origin)."""
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in self._ALLOWED_HOSTS:
                return False
            origin = self.headers.get("Origin")
            if origin is not None:
                oh = urlparse(origin).hostname or ""
                if oh not in self._ALLOWED_HOSTS:
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
            if self.path == "/":
                self._send(200, Path(html_path).read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/health":
                repo, commit = library.provenance()
                self._send_json(200, {"ok": True, "repo": repo, "commit": commit})
            elif self.path == "/status":
                self._send_json(200, library.status_snapshot())
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > self._MAX_BODY:
                self._send_json(413, {"error": "request too large"})
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


def serve(host: str = "127.0.0.1", port: int = 8000):
    load_env_file(REPO_ROOT / ".env")  # pick up keys from a gitignored .env
    default_repo, commit = resolve_provenance(CORPUS_META, QUESTIONS)
    library = Library(CORPUS_DIR, CACHE_ROOT, default_repo)
    require_auth = bool(os.environ.get("ICARUS_REQUIRE_GITHUB_AUTH"))
    verifier = GitHubTokenVerifier() if require_auth else None
    handler = make_handler(library, str(INDEX_HTML), require_auth=require_auth, verifier=verifier)
    httpd = ThreadingHTTPServer((host, port), handler)
    auth_note = "GitHub bearer required" if require_auth else "open (loopback only)"
    print(f"Icarus demo on http://{host}:{port}  (corpus: {default_repo} @ {commit[:12]}; auth: {auth_note})")
    print("Type any public owner/repo in the app to switch. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve()
