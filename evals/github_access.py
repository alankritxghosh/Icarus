# evals/github_access.py
"""Caller-scoped repo access check -- the permission gate in front of private
ingest. We ask GitHub 'can THIS token read THIS repo?' and refuse on anything
but a clean 200 (fail safe, like the honesty gate). The same response tells us
whether the repo is private, which routes writer + storage. The token is used
in-memory for one request header; never logged, never stored."""

import http.client
import json
import urllib.error
import urllib.request

_API = "https://api.github.com/repos/"
_USER_AGENT = "icarus/0.1"


def _default_opener(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


def _get_json(url, token, opener, timeout):
    """A fail-safe authenticated GET -> parsed JSON, or None on ANY problem.

    Shared by the two freshness probes below. Unlike `repo_info`, a missing
    token is allowed: those probes read PUBLIC repository state, and refusing
    without one would make freshness permanently unavailable on the web
    surface, whose login narrowed to `read:user` (2026-07-26)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with (opener or _default_opener)(urllib.request.Request(url, headers=headers), timeout) as resp:
            if getattr(resp, "status", None) != 200:
                return None
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError, TypeError, http.client.HTTPException):
        return None


def head_commit(repo: str, token: str = None, opener=None, timeout: float = 10.0):
    """The repo's current default-branch HEAD sha, or None if it can't be read.

    None means UNKNOWN and callers must render it that way. Reporting an index
    as up to date because the check failed is the same class of failure as a
    bluffed citation: a confident claim the evidence does not support."""
    if not repo:
        return None
    data = _get_json(f"{_API}{repo}/commits?per_page=1", token, opener, timeout)
    if not isinstance(data, list) or not data:
        return None
    sha = data[0].get("sha") if isinstance(data[0], dict) else None
    return sha if isinstance(sha, str) and sha else None


def commits_between(repo: str, base: str, head: str, token: str = None,
                    opener=None, timeout: float = 10.0):
    """How many commits `head` is ahead of `base`, or None if unknown.

    Asked only once the two shas are known to differ, so the common
    (up-to-date) case costs one request rather than two. `ahead_by` is
    GitHub's own count for base...head, which is what "N commits behind"
    means for an index pinned at `base`."""
    if not repo or not base or not head:
        return None
    data = _get_json(f"{_API}{repo}/compare/{base}...{head}", token, opener, timeout)
    if not isinstance(data, dict):
        return None
    ahead = data.get("ahead_by")
    # A bool is an int in Python; a JSON `true` here is malformed, not a count.
    return ahead if isinstance(ahead, int) and not isinstance(ahead, bool) else None


def repo_info(repo: str, token: str, opener=None, timeout: float = 10.0):
    """-> {"private": bool} iff GitHub answers 200 with a boolean `private`
    field for this token; None on ANY other outcome (403, 404, network error,
    malformed body, missing token). Never raises."""
    if not repo or not token:
        return None
    opener = opener or _default_opener
    req = urllib.request.Request(
        _API + repo,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener(req, timeout) as resp:
            if getattr(resp, "status", None) != 200:
                return None
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError, TypeError, http.client.HTTPException):
        return None
    private = data.get("private") if isinstance(data, dict) else None
    if not isinstance(private, bool):
        return None
    return {"private": private}
