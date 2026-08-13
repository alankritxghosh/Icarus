# demo/posthog_capture.py
"""Fire-and-forget PRODUCT usage capture for PostHog -- counts and identity
only. Never question text, code, citations, or answer content: this sits on
the same request path private-repo evidence flows through, so what it sends
is a deliberate, minimized decision (see CLAUDE.md's credential-boundary
rule), not the website's marketing snippet. Separate PostHog project from the
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

_PROJECT_TOKEN = os.environ.get("POSTHOG_PROJECT_TOKEN", "").strip()
_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com").strip().rstrip("/")


def capture(event, distinct_id, properties=None, opener=None, token=None):
    """Send one event on a daemon thread; no-ops when unconfigured and never
    raises into the request that triggered it (analytics must not be able to
    break or slow down an answer). Returns the thread (join it in tests);
    real callers ignore the return value. `opener`/`token` are injectable for
    offline tests -- default to the real urlopen and the env-configured key."""
    token = _PROJECT_TOKEN if token is None else token
    if not token:
        return None
    opener = opener or urllib.request.urlopen
    body = {
        "api_key": token,
        "event": event,
        "distinct_id": distinct_id or "anonymous",
        "properties": properties or {},
    }

    def _send():
        try:
            data = json.dumps(body).encode("utf-8")
            request = urllib.request.Request(
                f"{_HOST}/i/v0/e/", data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            opener(request, timeout=5).close()
        except Exception as e:  # analytics failing must never surface to a caller
            print(f"posthog capture failed: {type(e).__name__}: {e}", file=sys.stderr)

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    return thread
