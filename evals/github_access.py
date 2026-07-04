# evals/github_access.py
"""Caller-scoped repo access check -- the permission gate in front of private
ingest. We ask GitHub 'can THIS token read THIS repo?' and refuse on anything
but a clean 200 (fail safe, like the honesty gate). The same response tells us
whether the repo is private, which routes writer + storage. The token is used
in-memory for one request header; never logged, never stored."""

import json
import urllib.error
import urllib.request

_API = "https://api.github.com/repos/"
_USER_AGENT = "icarus/0.1"


def _default_opener(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


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
    except (urllib.error.URLError, OSError, ValueError, TypeError):
        return None
    private = data.get("private") if isinstance(data, dict) else None
    if not isinstance(private, bool):
        return None
    return {"private": private}
