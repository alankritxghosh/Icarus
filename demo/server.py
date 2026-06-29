# demo/server.py
"""A minimal local web face over the gated brain. Stdlib http.server only.

GET  /      -> the static demo page (demo/index.html)
POST /ask   -> {"question": "..."} -> the build_payload JSON for the page

The pipeline is built once in serve(); the request handler is a thin shell that
calls pipeline.answer(question) and renders the payload. No brain code changes
here -- this is packaging. Needs OPENROUTER_API_KEY (the writer) at runtime.

Run:  OPENROUTER_API_KEY=... python3 -m demo.server
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from evals.corpus import load_chunks
from evals.retriever import LexicalRetriever
from evals.provider import make_provider, has_provider_key
from evals.pipeline import GatedPipeline

from .payload import build_payload

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "evals" / "corpus" / "chunks.jsonl"
QUESTIONS = ROOT.parent / "evals" / "phase1_questions.json"
INDEX_HTML = ROOT / "index.html"


def make_handler(pipeline, repo: str, commit: str, html_path: str):
    """Build a request handler bound to a pipeline + corpus pin."""

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

        def do_GET(self):
            if self.path == "/":
                self._send(200, Path(html_path).read_bytes(), "text/html; charset=utf-8")
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/ask":
                self._send_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                question = data["question"]
            except (ValueError, KeyError, TypeError):
                self._send_json(400, {"error": "missing question"})
                return
            if not isinstance(question, str) or not question.strip():
                self._send_json(400, {"error": "missing question"})
                return
            payload = build_payload(pipeline.answer(question), repo, commit)
            self._send_json(200, payload)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000):
    corpus = json.loads(QUESTIONS.read_text())["corpus"]
    repo, commit = corpus["repo"], corpus["commit"]
    chunks = load_chunks(CORPUS)
    # Default writer = free Gemini (~1,500/day); fall back to OpenRouter only if
    # Gemini's key is absent. Public repos only on free hosted models.
    writer = "gemini" if has_provider_key("gemini") else "openrouter"
    pipeline = GatedPipeline(LexicalRetriever(chunks), chunks, make_provider(writer))
    handler = make_handler(pipeline, repo, commit, str(INDEX_HTML))
    httpd = HTTPServer((host, port), handler)
    print(f"Icarus demo on http://{host}:{port}  (corpus: {repo} @ {commit[:12]})")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve()
