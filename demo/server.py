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
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from evals.corpus_meta import load_meta

from .payload import build_payload
from .library import Library

ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT.parent / "evals" / "corpus"
CORPUS_META = CORPUS_DIR / "meta.json"
CACHE_ROOT = CORPUS_DIR / "cache"
QUESTIONS = ROOT.parent / "evals" / "phase1_questions.json"
INDEX_HTML = ROOT / "index.html"

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def make_handler(library, html_path: str):
    """Build a request handler bound to a Library (the active-repo state)."""

    class Handler(BaseHTTPRequestHandler):
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
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
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
    default_repo, commit = resolve_provenance(CORPUS_META, QUESTIONS)
    library = Library(CORPUS_DIR, CACHE_ROOT, default_repo)
    handler = make_handler(library, str(INDEX_HTML))
    httpd = HTTPServer((host, port), handler)
    print(f"Icarus demo on http://{host}:{port}  (corpus: {default_repo} @ {commit[:12]})")
    print("Type any public owner/repo in the app to switch. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve()
