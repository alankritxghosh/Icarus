#!/usr/bin/env python3
"""Manual, leak-safe smoke of the brain's PRIVATE-repo path over real HTTP --
the exact endpoints the Mac app's BrainClient drives: /status -> /connect ->
/status (poll) -> /ask -> /disconnect. This is the only check that exercises the
*server* private path live; the unit suite covers the ingest/provider layer.

Run against a brain started in auth mode (private routing only activates there):

    ICARUS_REQUIRE_GITHUB_AUTH=1 python3 -m demo.server   # in one shell

    GH_BEARER="$(gh auth token)" \
    ICARUS_PRIVATE_REPO=owner/name \
    python3 scripts/private_flow_smoke.py                  # in another

The GitHub token is read from the GH_BEARER env var and sent only in the
Authorization header -- never on a command line, never printed (an explicit
redaction guard scrubs it from any echoed body). It clones your private repo
onto the brain and sends chunks to the paid, private-safe writer -- point it at
a repo you're comfortable indexing. Exits non-zero on any failed assertion.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("ICARUS_BASE", "http://127.0.0.1:8000")
REPO = os.environ.get("ICARUS_PRIVATE_REPO")
TOKEN = os.environ.get("GH_BEARER")
QUESTION = os.environ.get(
    "ICARUS_QUESTION", "What does this project do and how is it structured?"
)

if not REPO or not TOKEN:
    sys.exit("set GH_BEARER (a GitHub token) and ICARUS_PRIVATE_REPO=owner/name")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def redact(d):
    # Defensive: never let the token echo into output even if the server changed.
    s = json.dumps(d)
    return json.loads(s.replace(TOKEN, "<redacted>")) if TOKEN in s else d


print("== 1. baseline /status (before connect) ==")
st, body = call("GET", "/status")
print(st, redact(body))
assert body.get("private") is False, "baseline should be the public default"

print("\n== 2. POST /connect (private repo, caller-scoped) ==")
st, body = call("POST", "/connect", {"repo": REPO})
print(st, redact(body))
assert st == 202, f"expected 202 indexing, got {st}: {body}"

print("\n== 3. poll /status until ready ==")
deadline = time.time() + 240
ready = None
while time.time() < deadline:
    time.sleep(3)
    st, body = call("GET", "/status")
    print("  ", body.get("state"), "repo=", body.get("repo"),
          "private=", body.get("private"), "err=", body.get("error"))
    if body.get("state") == "error":
        sys.exit("!! indexing failed")
    if body.get("state") == "ready" and body.get("repo", "").lower() == REPO.lower():
        ready = body
        break
assert ready is not None, "timed out waiting for the private repo to index"
assert ready.get("private") is True, "connected repo must report private=true"
print("  counts:", ready.get("counts"))

print("\n== 4. POST /ask (answered by the PAID private-safe writer) ==")
st, body = call("POST", "/ask", {"question": QUESTION})
print(st)
print("  verdict:", body.get("verdict"))
print("  answer:", (body.get("answer") or "")[:400])
print("  citations:", [c.get("ref") for c in body.get("citations", [])])
print("  searched:", body.get("searched", [])[:6])

print("\n== 5. POST /disconnect (deletes this user's data, back to default) ==")
st, body = call("POST", "/disconnect")
print(st, redact(body))
assert body.get("private") is False, "disconnect must return to the public default"
assert body.get("repo", "").lower() != REPO.lower(), "disconnect must drop the private repo"

print("\nOK: private-repo flow ran end to end.")
