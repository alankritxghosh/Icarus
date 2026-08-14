# demo/posthog_capture.py
"""Fire-and-forget PRODUCT usage capture for PostHog -- counts and identity
by default, and question/answer/evidence content ONLY when the caller
explicitly opted in with `X-Icarus-Share-Content: 1` (see
`demo/server.py::_share_content`). This sits on the same request path
private-repo evidence flows through, so what it sends is a deliberate,
minimized decision (see CLAUDE.md's credential-boundary rule), not the
website's marketing snippet. This module itself sends whatever properties it
is handed -- the decision lives at the call site, which is where the header
is visible. Separate PostHog project from the
website (POSTHOG_PROJECT_TOKEN here is the PRODUCT project's key, not the
one embedded in site/index.html and demo/index.html).

Stdlib only -- urllib, matching the rest of this codebase's provider clients
(evals/provider.py). No SDK, no new dependency.
"""

import json
import os
import sys
import threading
import urllib.request

_DEFAULT_HOST = "https://us.i.posthog.com"

# How many capture threads may be in flight at once. One thread per event is
# fine at this scale and lethal without a ceiling: a burst (or a hung PostHog)
# stacks threads until `Thread.start()` raises RuntimeError, and that used to
# escape into the request being served. Over this many, the event is DROPPED --
# analytics is the thing that gives way, never the answer.
_MAX_IN_FLIGHT = 32
_in_flight = 0
_in_flight_lock = threading.Lock()


def _config():
    """Read configuration at CALL time, not import time.

    `demo/server.py` imports this module at line 39 but only loads `.env`
    inside `serve()`, so reading the token into a module global at import left
    it permanently empty for the documented local `.env` setup -- analytics
    silently off, and a custom POSTHOG_HOST silently ignored. Shell- and
    PaaS-injected variables happened to work, which is why it went unnoticed.
    """
    return (
        os.environ.get("POSTHOG_PROJECT_TOKEN", "").strip(),
        os.environ.get("POSTHOG_HOST", _DEFAULT_HOST).strip().rstrip("/") or _DEFAULT_HOST,
    )


def capture(event, distinct_id, properties=None, opener=None, token=None):
    """Send one event on a daemon thread; no-ops when unconfigured and never
    raises into the request that triggered it (analytics must not be able to
    break or slow down an answer). Returns the thread (join it in tests);
    real callers ignore the return value. `opener`/`token` are injectable for
    offline tests -- default to the real urlopen and the env-configured key."""
    global _in_flight
    env_token, host = _config()
    if token is None:
        token = env_token
    if not token:
        return None
    opener = opener or urllib.request.urlopen
    body = {
        "api_key": token,
        "event": event,
        "distinct_id": distinct_id or "anonymous",
        "properties": properties or {},
    }

    with _in_flight_lock:
        if _in_flight >= _MAX_IN_FLIGHT:
            print("posthog capture dropped: too many in flight", file=sys.stderr)
            return None
        _in_flight += 1

    def _send():
        global _in_flight
        try:
            data = json.dumps(body).encode("utf-8")
            request = urllib.request.Request(
                f"{host}/i/v0/e/", data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            opener(request, timeout=5).close()
        except Exception as e:  # analytics failing must never surface to a caller
            print(f"posthog capture failed: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            with _in_flight_lock:
                _in_flight -= 1

    # Thread CREATION and start are inside the guard, not just the send. They
    # were outside it, so a `RuntimeError: cannot start new thread` propagated
    # out of capture() -- and `demo/server.py` calls capture BEFORE writing the
    # response, so analytics could stop the real answer from being sent.
    try:
        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
    except Exception as e:
        with _in_flight_lock:
            _in_flight -= 1
        print(f"posthog capture could not start: {type(e).__name__}: {e}",
              file=sys.stderr)
        return None
    return thread
