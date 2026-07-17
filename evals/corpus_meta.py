# evals/corpus_meta.py
"""Provenance for a generated corpus: which repo/commit/code-dir produced it.

Written next to chunks.jsonl by ingest.py and read by the demo so citation links
always point at the repo the corpus actually came from -- no second source of
truth to keep in sync. Data only; stdlib.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def write_meta(path, repo: str, commit: str, code_dir: str, counts: dict,
               chunking: str = "chunk_text") -> None:
    """`chunking` records which chunking scheme actually produced this
    corpus ("chunk_text" or "ast", see evals/ingest.py's CHUNKING_SCHEME_*
    constants) -- T6 of docs/plans/2026-07-17-ast-chunking-all-languages.md,
    read by demo/library.py's Library._resolve to detect a corpus chunked by
    a scheme that's since changed, so a later connect can re-ingest instead
    of silently serving a stale-but-internally-consistent corpus forever.
    Defaults to "chunk_text" (the scheme every corpus used before this field
    existed) so callers that don't care -- most tests -- don't need updating."""
    Path(path).write_text(json.dumps({
        "repo": repo,
        "commit": commit,
        "code_dir": code_dir,
        "counts": counts,
        "chunking": chunking,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n")


def load_meta(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())
