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
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_AGENT = "icarus/0.1"

# A Chrome extension's chrome.identity.launchWebAuthFlow redirect target is
# always https://<32-char id>.chromiumapp.org/ -- ids are exactly 32 lowercase
# letters in a-p (a base16-like alphabet Chrome uses for extension ids). This
# is the open-redirect guard for "extension" mode: without it, a caller could
# make the server redirect a just-completed login session to an arbitrary
# attacker-controlled URL instead of the genuine extension.
_CHROMIUMAPP_REDIRECT = re.compile(r"^https://[a-p]{32}\.chromiumapp\.org/$")

# Login scope per surface. Ask each surface for what it can actually use, and
# nothing more -- the consent screen is the first honest claim a stranger sees.
#
# The browser trial (`web`) only ever connects PUBLIC repositories, and a public
# repo needs no repository scope at all: the caller's token is used to identify
# them and to check, as them, that the repo is readable. So it asks for identity
# alone. A web user who tries to connect a PRIVATE repo is refused by
# demo/server.py's caller-scoped check -- correctly, and with a message that is
# true either way ("doesn't exist or your GitHub account can't read it").
#
# The native surfaces DO connect private repositories, which is the product, so
# they keep `repo` until the per-repo GitHub App replaces it (see authorize_url).
#
# Note this only narrows what NEW logins request. GitHub keeps the union of
# scopes already granted to an OAuth App, so anyone who previously authorised
# with `repo` keeps it until they revoke access in their GitHub settings.
_WEB_SCOPE = "read:user"
_NATIVE_SCOPE = "repo"


def new_state() -> str:
    """A URL-safe, unguessable token for CSRF `state` and session ids."""
    return secrets.token_urlsafe(24)


def authorize_url(client_id: str, redirect_uri: str, state: str, scope: str = "repo") -> str:
    """Build the GitHub authorize URL the app opens in the auth sheet.

    Scope `repo` lets a signed-in user connect their own PRIVATE repositories --
    the caller's token authenticates the private clone (see demo/server.py and
    evals/ingest.py's leak-safe env auth). Classic OAuth has no read-only private
    scope, so `repo` is broader than we'd like: it grants read/write to ALL of a
    user's private repos, not just the one they connect. This is a deliberate,
    disclosed tradeoff to unblock design partners; the trust-correct replacement
    is a GitHub App with per-repo, read-only installation (roadmap) so a customer
    grants exactly one repo, not their whole account. Change this default back to
    `read:user` if reverting to a public-only build.
    """
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
        # state -> (created_at, mode, redirect_target); redirect_target is
        # only ever non-None for mode == "extension".
        self._pending: dict[str, tuple[float, str, str | None]] = {}
        self._sessions: dict[str, tuple[str, float]] = {}  # session_id -> (token, created_at)
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._cid and self._secret)

    def begin(self, mode: str = "app", redirect_target: str | None = None) -> tuple[str, str]:
        """Mint a CSRF state (tagged with the login surface) and return
        (state, authorize_url). `mode` is "app" (Mac app -> icarus:// callback),
        "web" (browser -> same-origin page), or "extension" (a browser
        extension's chrome.identity.launchWebAuthFlow -> its own
        https://<id>.chromiumapp.org/ redirect target, required and validated
        for that mode -- see _CHROMIUMAPP_REDIRECT's docstring for why).
        `redirect_target` is ignored (never stored) for any mode other than
        "extension" -- only that mode's callback ever reads it back.

        The requested SCOPE also depends on the mode: the browser trial asks for
        identity only, the native surfaces ask for repository access, because
        only they can connect a private repo. See _WEB_SCOPE/_NATIVE_SCOPE."""
        if mode == "extension":
            if not redirect_target or not _CHROMIUMAPP_REDIRECT.match(redirect_target):
                raise ValueError("extension mode requires a valid chromiumapp.org redirect_target")
        else:
            redirect_target = None
        scope = _WEB_SCOPE if mode == "web" else _NATIVE_SCOPE
        state = new_state()
        with self._lock:
            self._sweep()
            self._pending[state] = (time.time(), mode, redirect_target)
        return state, authorize_url(self._cid, self._redirect, state, scope=scope)

    def complete(self, state: str, code: str) -> tuple[str, str, str | None]:
        """Validate the state, exchange the code, store the token under a fresh
        session id, and return (session_id, mode, redirect_target).
        `redirect_target` is None except for "extension" mode. Raises
        ValueError on an unknown/expired state."""
        with self._lock:
            self._sweep()
            entry = self._pending.pop(state, None)
            if entry is None:
                raise ValueError("unknown or expired state")
        _created, mode, redirect_target = entry
        token = self._exchange(  # network happens outside the lock
            code, client_id=self._cid, client_secret=self._secret, redirect_uri=self._redirect)
        session_id = new_state()
        with self._lock:
            self._sessions[session_id] = (token, time.time())
        return session_id, mode, redirect_target

    def redeem(self, session_id: str) -> str | None:
        """Return the token for a session id exactly once, else None."""
        with self._lock:
            self._sweep()
            entry = self._sessions.pop(session_id, None)
        return entry[0] if entry else None

    def _sweep(self):
        now = time.time()
        self._pending = {s: v for s, v in self._pending.items() if now - v[0] < self._ttl}
        self._sessions = {s: v for s, v in self._sessions.items() if now - v[1] < self._ttl}
