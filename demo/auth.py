# demo/auth.py
"""Bearer-token auth for the brain's write/read endpoints.

When the server runs with ICARUS_REQUIRE_GITHUB_AUTH set (the mode the Mac app
uses), /ask and /connect require a valid GitHub access token in the
Authorization header. Verification proves *identity*, not just validity: the
verifier resolves the token to the caller's stable numeric GitHub user id by
calling GitHub's own /user endpoint — we never assert an identity GitHub hasn't
asserted first. Resolved identities are cached briefly so we don't hit GitHub
on every request.

Fail-safe by construction: no token, a malformed header, a network error, any
non-200 from GitHub, or an unparseable body all map to "no identity" (None). We
never authorize on ambiguity.

The verifier is injected so the unit suite stays offline (StaticTokenVerifier).
The plain web demo runs WITHOUT this (loopback + Host/Origin guard is its
protection); auth is opt-in via the env flag.
"""

import json
import time
import urllib.error
import urllib.request

from evals import github_access


def bearer_token(headers) -> str | None:
    """Extract the token from an `Authorization: Bearer <token>` header, else None."""
    raw = headers.get("Authorization") if headers else None
    if not raw:
        return None
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


class TokenVerifier:
    def verify(self, token: str) -> str | None:  # pragma: no cover - interface
        """Return the caller's stable user id, or None (fail safe)."""
        raise NotImplementedError


class StaticTokenVerifier(TokenVerifier):
    """Test double: maps allowed tokens to user ids. A set/list input means each
    token is its own id (for tests that don't care about the id value)."""

    def __init__(self, allowed):
        self._allowed = dict(allowed) if isinstance(allowed, dict) else {t: t for t in allowed}

    def verify(self, token: str) -> str | None:
        return self._allowed.get(token) if token else None


class GitHubTokenVerifier(TokenVerifier):
    """Resolves a token to the caller's stable numeric GitHub user id via
    GET /user. Caches token -> (id, expiry) for `ttl` seconds. Any error,
    non-200, or unparseable body => None (fail safe — never an identity we
    haven't seen GitHub assert)."""

    URL = "https://api.github.com/user"

    def __init__(self, ttl: float = 300.0, timeout: float = 10.0):
        self._ttl = ttl
        self._timeout = timeout
        self._cache: dict[str, tuple[str, float]] = {}

    def verify(self, token: str) -> str | None:
        if not token:
            return None
        now = time.time()
        entry = self._cache.get(token)
        if entry is not None and entry[1] > now:
            return entry[0]
        req = urllib.request.Request(
            self.URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "icarus/0.1",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status != 200:
                    return None
                user_id = str(json.loads(resp.read())["id"])
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            return None
        self._cache[token] = (user_id, now + self._ttl)
        return user_id


class RepoAccessVerifier:
    """Can THIS caller read THIS repo, right now — asked of GitHub, not modelled here.

    This is the entitlement check for a SHARED per-repo index. Once a corpus is
    shared, the storage layout stops being the isolation and this becomes it.

    Deliberately no org/team/membership model. GitHub already knows who may read
    a repo and is authoritative; any membership list we kept would be a second
    copy that can go stale, and a stale access list is a breach. Asking GitHub
    each time also makes offboarding free: access revoked there, refused here,
    with no code of ours involved.

    Answers are cached per (repo, token) for `ttl` seconds so a busy team does
    not exhaust GitHub's rate limit. The accepted cost, decided 2026-07-27: a
    caller whose access is revoked keeps it for up to `ttl` (default 5 minutes).
    That window is the only reason this class holds any state at all.

    Fail-safe in one direction only: no token, a refusal, a network error, or an
    exception all mean DENIED. Wrongly denying is an outage; wrongly allowing
    hands one company's private code to another.
    """

    def __init__(self, access_fn=None, ttl: float = 300.0, clock=time.time):
        self._access = access_fn or github_access.repo_info
        self._ttl = ttl
        self._clock = clock
        # (repo, token) -> (allowed, expiry). Keyed on the TOKEN as well as the
        # repo: keying on repo alone would let the first authorised reader
        # silently unlock that repo for every other caller.
        self._cache: dict[tuple[str, str], tuple[bool, float]] = {}

    def can_read(self, repo: str, token: str | None) -> bool:
        if not repo or not token:
            return False  # never ask GitHub to authorise an anonymous caller
        key = (repo, token)
        now = self._clock()
        entry = self._cache.get(key)
        if entry is not None and entry[1] > now:
            return entry[0]
        try:
            allowed = self._access(repo, token) is not None
        except Exception:
            return False  # an outage denies; it does not raise and does not allow
        self._cache[key] = (allowed, now + self._ttl)
        return allowed
