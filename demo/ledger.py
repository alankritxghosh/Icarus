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

**What is stored, and what is not.** Question text, verdict, citation refs, and
a timestamp. Storing question text at all is a deliberate decision (2026-07-27)
and the privacy promise must say so before this ships.

NOT the answer body: regenerable from the corpus, the largest field, and
retaining it would widen the privacy surface for nothing the unknowns map needs.

NOT who asked. This maps what an ORGANISATION has not written down; it does not
track which employee asked what. Recording the asker would make "Alice asked
about auth fourteen times" a question this system can answer, which is a
different product -- surveillance of a team rather than memory for it. The cost
is accepted and real: gaps can be ranked by how OFTEN they were hit, never by
how many DISTINCT people hit them.

Format is JSONL, append-only, one file per repo -- the same shape as the corpus
itself, and readable with nothing but the standard library.
"""

import hashlib
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


def normalize_question(question: str) -> str:
    """The one exact-text identity used by listing, recording, and resolution."""
    return question.strip().casefold()


def memory_gap_id(repo: str, question: str) -> str:
    normalized = normalize_question(question)
    if not normalized:
        raise ValueError("question is required")
    material = f"{repo.casefold()}\0{normalized}".encode()
    return hashlib.sha256(material).hexdigest()


class Ledger:
    """Append-only per-repo record of asks. Thread-safe; safe to construct many."""

    def __init__(self, root):
        self._root = Path(root)
        self._lock = threading.Lock()

    def _path(self, repo: str) -> Path:
        return self._root / f"{_slug(repo)}.jsonl"

    def record(self, repo: str, *, question: str, verdict: str,
               citations=(), reason=None) -> None:
        """Append one ask. Never raises on a full disk or a racing writer taking
        the record down with it -- a failed ledger write must not fail the
        answer the caller actually asked for.

        Deliberately takes no identity: see the module docstring."""
        path = self._path(repo)          # validates BEFORE any filesystem work
        entry = {
            "ts": time.time(),
            "question": question,
            "verdict": verdict,
            "citations": list(citations or ()),
            # WHY the gate abstained (evals/gate.py's ABSTAIN_* constants), so
            # the unknowns map is a real map of documentation debt rather than a
            # pile of every question that failed for any reason. Without it,
            # "nobody wrote this down" and "you asked about something that does
            # not exist here" are indistinguishable, and a typo inflates a
            # team's apparent debt. None on an answer, and on any entry written
            # before this field existed.
            "reason": reason,
        }
        self._append(path, entry, required=False)

    def record_proposal(self, repo: str, *, gap_id: str, question: str,
                        result: dict) -> None:
        """Persist an observed GitHub proposal before the API claims success."""
        path = self._path(repo)
        if gap_id != memory_gap_id(repo, question):
            raise ValueError("gap id does not match question")
        if not isinstance(result, dict):
            raise ValueError("proposal result is required")
        proposal = {
            key: result.get(key)
            for key in (
                "repo", "question", "branch", "path", "file_url",
                "pull_request_url",
            )
        }
        if (
            proposal["repo"] != repo
            or proposal["question"] != question
            or not isinstance(proposal["branch"], str)
            or not isinstance(proposal["path"], str)
            or not isinstance(proposal["pull_request_url"], str)
            or not proposal["pull_request_url"].startswith("https://github.com/")
        ):
            raise ValueError("invalid proposal result")
        entry = {
            "ts": time.time(),
            "question": question,
            "verdict": "proposal",
            "gap_id": gap_id,
            "proposal": proposal,
        }
        self._append(path, entry, required=True)

    def _append(self, path: Path, entry: dict, *, required: bool) -> None:
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
            if required:
                raise
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

    def gaps(self, repo: str, *, include_resolved: bool = False):
        """Collapse the repo's asks into exact-text engineering-memory gaps.

        A gap begins with an unknown verdict. It is resolved only when the latest
        ask of that same normalized question is an answer carrying at least one
        citation. An answer-shaped row with no receipt cannot repair
        organizational knowledge.

        Matching is deliberately literal after trim+casefold. Semantic
        clustering would risk merging distinct decisions and claiming the wrong
        gap was resolved.
        """
        # `entries` is newest-first; process oldest-first so the last matching
        # row is the actual current state. This beta already reads the whole
        # JSONL file in `entries`, so a generous bound changes no resource shape.
        chronological = reversed(self.entries(repo, limit=1_000_000))
        grouped = {}
        for entry in chronological:
            question = entry.get("question")
            if not isinstance(question, str):
                continue
            display = question.strip()
            if not display:
                continue
            key = normalize_question(display)
            gap_id = memory_gap_id(repo, display)
            verdict = entry.get("verdict")
            citations = entry.get("citations")
            citations = citations if isinstance(citations, list) else []
            ts = entry.get("ts")
            ts = float(ts) if isinstance(ts, (int, float)) else 0.0

            gap = grouped.get(key)
            if verdict == "unknown":
                reason = entry.get("reason")
                if gap is None:
                    gap = grouped[key] = {
                        "question": display,
                        "id": gap_id,
                        "unknown_count": 0,
                        "last_asked": ts,
                        "status": "open",
                        "kind": "unclear",
                        "actionable": False,
                        "resolution_citations": [],
                        "proposal": None,
                    }
                was_proposed = gap["status"] == "proposed"
                gap["unknown_count"] += 1
                gap["last_asked"] = max(gap["last_asked"], ts)
                if not was_proposed:
                    gap["status"] = "open"
                    gap["resolution_citations"] = []
                    gap["proposal"] = None
                    if reason == "no_recorded_reason":
                        gap["kind"] = "undocumented"
                        gap["actionable"] = True
                    elif reason == "entity_absent":
                        gap["kind"] = "not_in_repo"
                        gap["actionable"] = False
                    else:
                        gap["kind"] = "unclear"
                        gap["actionable"] = False
            elif verdict == "proposal" and gap is not None:
                proposal = entry.get("proposal")
                if (
                    entry.get("gap_id") == gap_id
                    and isinstance(proposal, dict)
                    and isinstance(proposal.get("pull_request_url"), str)
                    and proposal["pull_request_url"].startswith("https://github.com/")
                    and gap["status"] != "resolved"
                ):
                    gap["status"] = "proposed"
                    gap["actionable"] = False
                    gap["proposal"] = proposal
                    gap["last_asked"] = max(gap["last_asked"], ts)
            elif gap is not None:
                gap["last_asked"] = max(gap["last_asked"], ts)
                if verdict == "answer" and citations:
                    gap["status"] = "resolved"
                    gap["actionable"] = False
                    gap["resolution_citations"] = citations
                elif gap["status"] != "proposed":
                    # A malformed "answer" with no citations cannot resolve the
                    # gap; leave it open and preserve its last honest kind.
                    gap["status"] = "open"
                    gap["resolution_citations"] = []

        gaps = [
            gap for gap in grouped.values()
            if include_resolved or gap["status"] != "resolved"
        ]
        return sorted(
            gaps,
            key=lambda gap: (-gap["unknown_count"], -gap["last_asked"], gap["question"]),
        )
