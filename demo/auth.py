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
