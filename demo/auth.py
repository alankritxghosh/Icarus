# demo/auth.py
"""Bearer-token auth for the brain's write/read endpoints.

When the server runs with ICARUS_REQUIRE_GITHUB_AUTH set (the mode the Mac app
uses), /ask and /connect require a valid GitHub access token in the
Authorization header. Validity is proven by calling GitHub's own /user endpoint
with the token — we never trust a token we haven't seen GitHub accept. Valid
tokens are cached briefly so we don't hit GitHub on every request.

Fail-safe by construction: no token, a malformed header, a network error, or any
non-200 from GitHub all map to "not authorized". We never authorize on ambiguity.

The verifier is injected so the unit suite stays offline (StaticTokenVerifier).
The plain web demo runs WITHOUT this (loopback + Host/Origin guard is its
protection); auth is opt-in via the env flag.
"""

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
    def verify(self, token: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class StaticTokenVerifier(TokenVerifier):
    """Test double: authorizes exactly the tokens in the allowed set."""

    def __init__(self, allowed):
        self._allowed = set(allowed)

    def verify(self, token: str) -> bool:
        return bool(token) and token in self._allowed


class GitHubTokenVerifier(TokenVerifier):
    """Validates a token by calling GitHub GET /user. Caches valid tokens for
    `ttl` seconds. Any error or non-200 => not authorized (fail safe)."""

    URL = "https://api.github.com/user"

    def __init__(self, ttl: float = 300.0, timeout: float = 10.0):
        self._ttl = ttl
        self._timeout = timeout
        self._cache: dict[str, float] = {}

    def verify(self, token: str) -> bool:
        if not token:
            return False
        now = time.time()
        expiry = self._cache.get(token)
        if expiry is not None and expiry > now:
            return True
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
                ok = resp.status == 200
        except (urllib.error.URLError, OSError):
            return False
        if ok:
            self._cache[token] = now + self._ttl
        return ok
