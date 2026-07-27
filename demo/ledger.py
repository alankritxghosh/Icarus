# demo/ledger.py
"""The per-repo ask ledger: what a team asked, and what nobody had written down.

This is the piece that makes Icarus a company's brain rather than a shared
search box. Every question and its verdict is recorded against the REPO, not the
person, so a team accumulates one record instead of N private histories.

The subset with verdict "unknown" is the artifact worth having: a live map of an
organisation's undocumented knowledge, ranked by how often people needed it. No
other tool can produce it, because producing it requires being willing to say
"I don't know" in the first place.

**It deliberately lives OUTSIDE the corpus directory.** `registry._ingest_once`
publishes a corpus with `os.replace()`, which swaps the whole directory -- a
ledger stored inside would be silently destroyed by the next re-index, taking
the team's accumulated history with it.

**What is stored, and what is not.** Question text, verdict, citation refs, the
asking identity, and a timestamp. NOT the answer body: it is regenerable from
the corpus, it is the largest field, and retaining it would widen the privacy
surface for no gain the unknowns map needs. Storing question text at all is a
deliberate decision (2026-07-27) and the privacy promise must say so before this
ships.

Format is JSONL, append-only, one file per repo -- the same shape as the corpus
itself, and readable with nothing but the standard library.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

# Mirrors demo/library._slug: "owner/name" -> "owner__name". Repo names are
# validated at the HTTP edge too, but this must not be the only guard.
_SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _slug(repo: str) -> str:
    if not repo or not _SAFE_REPO.match(repo) or ".." in repo:
        raise ValueError("invalid repo name")
    return repo.replace("/", "__")


class Ledger:
    """Append-only per-repo record of asks. Thread-safe; safe to construct many."""

    def __init__(self, root):
        self._root = Path(root)
        self._lock = threading.Lock()

    def _path(self, repo: str) -> Path:
        return self._root / f"{_slug(repo)}.jsonl"

    def record(self, repo: str, *, user: str, question: str, verdict: str,
               citations=()) -> None:
        """Append one ask. Never raises on a full disk or a racing writer taking
        the record down with it -- a failed ledger write must not fail the
        answer the user actually asked for."""
        path = self._path(repo)          # validates BEFORE any filesystem work
        entry = {
            "ts": time.time(),
            "user": user,
            "question": question,
            "verdict": verdict,
            "citations": list(citations or ()),
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                self._root.mkdir(parents=True, exist_ok=True)
                # Append mode + one write per line: the lock serialises writers in
                # this process, and O_APPEND keeps a second replica on a shared
                # volume from overwriting rather than appending.
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError:
            pass  # the ledger is an asset, not a dependency of answering

    def entries(self, repo: str, *, limit: int = 100, unknowns_only: bool = False):
        """Most recent first. A missing ledger reads as empty, not an error.

        ponytail: reads the whole file and reverses. Fine at a beta's volume;
        if a repo's ledger ever gets large, switch to a reverse line reader or
        an index rather than growing this.
        """
        path = self._path(repo)
        try:
            raw = path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return []
        out = []
        for line in reversed(raw):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # a torn line must not poison the whole record
            if unknowns_only and entry.get("verdict") != "unknown":
                continue
            out.append(entry)
            if len(out) >= limit:
                break
        return out
