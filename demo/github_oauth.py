# demo/github_oauth.py
"""Server-side GitHub OAuth (authorization-code) flow for the web login.

The Mac app opens GitHub's login in a sheet; GitHub redirects to the brain's
loopback callback; the brain exchanges the code for a token using the client
SECRET (which lives only here, in the brain's env — never in the app), then bounces
the sheet closed with an `icarus://` redirect. The app redeems a one-time session
id for the token and holds it in memory. Stdlib only.

State is single-use CSRF protection; sessions are single-use with a short TTL. The
GitHub token never travels in a redirect URL — only the opaque session id does.
"""

import json
import secrets
import threading
import time
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_AGENT = "icarus/0.1"


def new_state() -> str:
    """A URL-safe, unguessable token for CSRF `state` and session ids."""
    return secrets.token_urlsafe(24)


def authorize_url(client_id: str, redirect_uri: str, state: str, scope: str = "read:user") -> str:
    """Build the GitHub authorize URL the app opens in the auth sheet."""
    q = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "allow_signup": "false",
    })
    return f"{AUTHORIZE_URL}?{q}"


def _default_opener(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


def exchange_code(code: str, *, client_id: str, client_secret: str, redirect_uri: str,
                  opener=None, timeout: float = 15.0) -> str:
    """POST the code to GitHub's token endpoint and return the access token.
    `opener(req, timeout)` is injected so unit tests stay offline. Raises on any
    error body or a missing token (fail safe — never return an empty token)."""
    opener = opener or _default_opener
    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
    )
    with opener(req, timeout) as resp:
        data = json.loads(resp.read())
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"github token exchange failed: {data.get('error', 'no access_token')}")
    return token


class OAuthFlow:
    """In-memory orchestrator: begin → complete (exchange) → redeem. Thread-safe.
    Holds the client id/secret/redirect; single-use state + sessions with a TTL."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 *, ttl: float = 600.0, exchanger=exchange_code):
        self._cid = client_id
        self._secret = client_secret
        self._redirect = redirect_uri
        self._ttl = ttl
        self._exchange = exchanger
        self._pending: dict[str, float] = {}      # state -> created_at
        self._sessions: dict[str, tuple[str, float]] = {}  # session_id -> (token, created_at)
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._cid and self._secret)

    def begin(self) -> tuple[str, str]:
        """Mint a CSRF state and return (state, authorize_url)."""
        state = new_state()
        with self._lock:
            self._sweep()
            self._pending[state] = time.time()
        return state, authorize_url(self._cid, self._redirect, state)

    def complete(self, state: str, code: str) -> str:
        """Validate the state, exchange the code, store the token under a fresh
        session id, and return it. Raises ValueError on an unknown/expired state."""
        with self._lock:
            self._sweep()
            if state not in self._pending:
                raise ValueError("unknown or expired state")
            del self._pending[state]
        token = self._exchange(  # network happens outside the lock
            code, client_id=self._cid, client_secret=self._secret, redirect_uri=self._redirect)
        session_id = new_state()
        with self._lock:
            self._sessions[session_id] = (token, time.time())
        return session_id

    def redeem(self, session_id: str) -> str | None:
        """Return the token for a session id exactly once, else None."""
        with self._lock:
            self._sweep()
            entry = self._sessions.pop(session_id, None)
        return entry[0] if entry else None

    def _sweep(self):
        now = time.time()
        self._pending = {s: t for s, t in self._pending.items() if now - t < self._ttl}
        self._sessions = {s: v for s, v in self._sessions.items() if now - v[1] < self._ttl}
