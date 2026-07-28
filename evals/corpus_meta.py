# evals/corpus_meta.py
"""Provenance for a generated corpus: which repo/commit/code-dir produced it.

Written next to chunks.jsonl by ingest.py and read by the demo so citation links
always point at the repo the corpus actually came from -- no second source of
truth to keep in sync. Data only; stdlib.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# Bump when ingest's OUTPUT SHAPE changes for any source, so an already-cached
# corpus re-ingests on its next connect instead of silently serving the old
# shape forever. `chunking` alone can't carry this: it records the CODE chunker
# only, so a change to how PR/issue chunks are built would leave it identical
# and the fix would ship live and be invisible to every connected repo.
#   1 -> 2 (2026-07-28): PR/issue chunks gained the discussion -- comments,
#          reviews, changed files, state/author -- not just title + body.
#   2 -> 3 (2026-07-28): EVERY PR and issue is indexed, not the most recent
#          200/500. On psf/requests that is 7,254 items instead of 700, so a
#          version-2 corpus is not merely older-shaped, it is 90% absent.
CORPUS_FORMAT_VERSION = 3

# A corpus written before the field existed is necessarily the original shape.
_PRE_VERSIONED_CORPUS = 1


def write_meta(path, repo: str, commit: str, code_dir: str, counts: dict,
               chunking: str = "chunk_text", truncated: bool = False) -> None:
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
        "corpus_version": CORPUS_FORMAT_VERSION,
        # True when a size cap (bytes/chunks) stopped the code walk early, so the
        # corpus is PARTIAL -- surfaced to the user (never silently "complete").
        "truncated": truncated,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n")


def load_meta(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def corpus_version(meta) -> int:
    """The format version a corpus was written with. A pre-versioned corpus
    (no field, or a non-integer someone hand-edited in) reads as version 1 --
    stale, which is the safe direction: it triggers a re-ingest rather than
    serving an old shape as if it were current."""
    value = (meta or {}).get("corpus_version", _PRE_VERSIONED_CORPUS)
    return value if isinstance(value, int) and not isinstance(value, bool) else _PRE_VERSIONED_CORPUS
