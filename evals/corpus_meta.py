# evals/corpus_meta.py
"""Provenance for a generated corpus: which repo/commit/code-dir produced it.

Written next to chunks.jsonl by ingest.py and read by the demo so citation links
always point at the repo the corpus actually came from -- no second source of
truth to keep in sync. Data only; stdlib.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def write_meta(path, repo: str, commit: str, code_dir: str, counts: dict) -> None:
    Path(path).write_text(json.dumps({
        "repo": repo,
        "commit": commit,
        "code_dir": code_dir,
        "counts": counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n")


def load_meta(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())
