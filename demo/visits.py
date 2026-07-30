# demo/visits.py
"""What Icarus remembers about a returning user: four facts, and no fifth.

Implements `docs/decisions/2026-07-30-returning-user-state.md`. Read that
before changing anything here -- the shape of this module is a privacy
decision, not an engineering preference.

    user identity            the directory this file lives in
    repository identity      a key inside it
    last-seen commit         the anchor a briefing is computed FROM
    last-visit timestamp     so "since you were last here" can be said in words

## What is deliberately absent

**No questions, ever.** `demo/ledger.py` records questions against the REPO
with no identity; this records identity with no questions. Neither store alone
can produce a per-person question history, and **they must never be joined**.
That separation is the entire safety property, and it is why this is a new
store rather than a user-id column added to the ledger.

`record()` therefore takes no question, answer, verdict or citation parameter.
A signature that cannot accept one is a stronger guarantee than a policy
saying we will not pass one.

**No activity trail.** A visit OVERWRITES the previous record rather than
appending to it. A list of timestamps is an activity log however innocuous
each row looks, and the decision doc forbids one. The accepted cost is that
Icarus cannot answer "how often does this person come back" -- deliberately,
permanently.

## Two properties inherited from the rest of the codebase

- **Never on the answering path.** A corrupt file, a full disk or a racing
  writer degrades to "first visit"; it never raises into a request. This is an
  asset, not a dependency -- the same rule `demo/ledger.py` holds to.
- **Inside the caller's own storage directory**, which is exactly what
  `LibraryRegistry.disconnect` deletes. "Deletable, and actually deleted"
  needs no second mechanism, and a test pins that it really goes.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

# Mirrors registry._SAFE_ID: ids come from GitHub, but this must not be the
# only guard -- a traversal here would write outside the user's own tree.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
# Mirrors ledger._SAFE_REPO.
_SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

_FILENAME = "visits.json"


def _safe_user(user_id):
    if not user_id or not _SAFE_ID.match(str(user_id)):
        raise ValueError("invalid user id")
    return str(user_id)


def _safe_repo(repo):
    if not repo or not _SAFE_REPO.match(repo) or ".." in repo:
        raise ValueError("invalid repo name")
    return repo


class VisitStore:
    """Durable per-user last-visit state. Thread-safe; safe to construct many.

    Durable is the point: `LibraryRegistry._last_repo` is an in-process dict
    that does not survive a deploy, so returning-user state built on it would
    reset every time we shipped -- which is most of the time.
    """

    def __init__(self, root, now=None):
        self._root = Path(root)
        self._now = now or time.time
        self._lock = threading.Lock()

    def _path(self, user_key):
        return self._root / user_key / _FILENAME

    def _read(self, user_key):
        try:
            data = json.loads(self._path(user_key).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def record(self, user_id, repo, commit):
        """Mark this user as having seen `repo` at `commit`, now.

        Takes no question, answer, verdict or citation -- see the module
        docstring. Never raises on a write failure.
        """
        user_key = _safe_user(user_id)
        repo = _safe_repo(repo)
        with self._lock:
            state = self._read(user_key)
            state[repo] = {"commit": commit, "at": self._now()}
            path = self._path(user_key)
            tmp = path.with_suffix(".tmp")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps(state), encoding="utf-8")
                # Atomic publish: a reader never sees a half-written file, and
                # a crash mid-write leaves the previous record intact.
                os.replace(tmp, path)
            except (OSError, ValueError):
                pass  # an asset, not a dependency of answering

    def last_visit(self, user_id, repo):
        """-> {"commit": ..., "at": ...} or None for a first visit.

        A missing, unreadable or corrupt file reads as None. "I have no record
        of you" is the honest degraded answer; raising into a request is not.
        """
        user_key = _safe_user(user_id)
        repo = _safe_repo(repo)
        entry = self._read(user_key).get(repo)
        if not isinstance(entry, dict):
            return None
        commit, at = entry.get("commit"), entry.get("at")
        if not isinstance(commit, str) or not isinstance(at, (int, float)):
            return None
        return {"commit": commit, "at": float(at)}
