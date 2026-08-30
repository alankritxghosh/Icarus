"""Short-lived, repository-bound session tokens for coding-agent clients.

The store holds only the verified GitHub user id and repository scope. The
GitHub credential used to mint a session is never passed in, retained, logged,
or written to disk. A grant can append only a bounded Agent Mode decision
candidate/no-decision acknowledgement in addition to its read routes; it can
never confirm a decision or mutate GitHub.

Scope covers public AND private repositories since 2026-08-07 (see
docs/decisions/2026-08-07-mcp-private-repository-access.md). A grant is still
bound to one identity and the one repo that identity had connected, and every
request re-checks entitlement -- what changed is that a private repo is no
longer refused outright.
"""

import secrets
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentGrant:
    identity: str
    repo: str


class AgentSessionStore:
    def __init__(self, ttl=600.0, clock=time.time, max_sessions=4096):
        if ttl <= 0 or max_sessions < 1:
            raise ValueError("ttl and max_sessions must be positive")
        self._ttl = float(ttl)
        self._clock = clock
        self._max = int(max_sessions)
        self._sessions = {}
        self._lock = threading.Lock()

    def _purge(self, now):
        expired = [
            token for token, (_grant, expiry) in self._sessions.items()
            if expiry <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)

    def issue(self, identity, repo):
        if not isinstance(identity, str) or not identity:
            raise ValueError("identity is required")
        if not isinstance(repo, str) or not repo:
            raise ValueError("repo is required")
        now = self._clock()
        expires_at = now + self._ttl
        grant = AgentGrant(identity=identity, repo=repo)
        with self._lock:
            self._purge(now)
            while len(self._sessions) >= self._max:
                oldest = min(
                    self._sessions,
                    key=lambda token: self._sessions[token][1],
                )
                self._sessions.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            while token in self._sessions:  # defensive; collisions are remote
                token = secrets.token_urlsafe(32)
            self._sessions[token] = (grant, expires_at)
        return token, expires_at

    def verify(self, token):
        if not token:
            return None
        now = self._clock()
        with self._lock:
            self._purge(now)
            entry = self._sessions.get(token)
            return entry[0] if entry is not None else None
