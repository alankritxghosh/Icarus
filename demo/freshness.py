# demo/freshness.py
"""Does the connected index still match the repository?

A connected repo's corpus is frozen at the commit it was ingested. Nothing
told anyone that. This repo's own index sat NINE COMMITS behind HEAD while
answering questions with complete confidence, and the only reason it was
noticed was that someone happened to add a file and go looking for it.

That is the same failure this product exists to avoid, moved out of citations
and into time: every answer was grounded in evidence genuinely retrieved from
a corpus that no longer described the repository.

## The one property everything here is arranged around

**"I could not check" must never render as "up to date".** `up_to_date` is
three-valued -- True, False, or **None for unknown** -- and every failure path
lands on None. A network blip, a revoked token, a rate limit: all unknown,
none of them reassuring. Telling someone their index is current when we did
not manage to look is a confident claim the evidence does not support, which
is the thing this codebase refuses to do everywhere else.

One deliberate exception, in the other direction: if HEAD is readable and
DIFFERS from the indexed commit but the comparison call then fails,
`up_to_date` stays **False** and only `behind_by` is None. We genuinely know
it differs; downgrading that to unknown would discard a fact we hold.

## Why it is cached

`/status` is polled continuously by the Mac app, and GitHub's API is not. The
result is cached per (repo, indexed commit) for a TTL, and `checked_at`
reports when the check ACTUALLY ran -- not now -- so a reader knows the
verdict may be minutes old. Keying on the indexed commit as well as the repo
means a refresh invalidates the entry immediately: otherwise the moment a user
finishes a refresh and looks at the banner to watch it clear is exactly the
moment they would be shown the pre-refresh verdict.

The caller's token is used for the request and never stored -- a checker is
shared across a repo's users, so a retained token would be one caller's
credential spent on another's request.
"""

import threading

from evals import github_access

_DEFAULT_TTL = 600.0  # seconds; a repo does not drift meaningfully faster


def _unknown(checked_at=None):
    """Every key present on every path, so a client can never KeyError its way
    into rendering nothing."""
    return {"up_to_date": None, "behind_by": None,
            "head_commit": None, "checked_at": checked_at}


class FreshnessChecker:
    """Thread-safe, TTL-cached staleness lookups for connected repos."""

    def __init__(self, head_fn=None, between_fn=None, now=None, ttl=_DEFAULT_TTL):
        self._head = head_fn or (lambda repo, token: github_access.head_commit(repo, token))
        self._between = between_fn or (
            lambda repo, base, target, token: github_access.commits_between(repo, base, target, token))
        if now is None:
            import time
            now = time.time
        self._now = now
        self._ttl = ttl
        self._cache = {}
        self._lock = threading.Lock()

    def check(self, repo, indexed_commit, token):
        """-> {up_to_date, behind_by, head_commit, checked_at}. Never raises.

        `token` is used for this request only and is never written to the
        cache, which is keyed on (repo, indexed_commit) alone.
        """
        if not repo or not indexed_commit:
            return _unknown()

        key = (repo, indexed_commit)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and self._now() - cached["checked_at"] < self._ttl:
                return dict(cached)

        checked_at = self._now()
        head = self._head(repo, token)
        if not head:
            # Unknown: NOT reported as up to date, and deliberately NOT cached
            # either -- a failed check should be retried on the next poll
            # rather than pinned for the whole TTL.
            return _unknown(checked_at)

        if head == indexed_commit:
            result = {"up_to_date": True, "behind_by": 0,
                      "head_commit": head, "checked_at": checked_at}
        else:
            behind = self._between(repo, indexed_commit, head, token)
            result = {"up_to_date": False, "behind_by": behind,
                      "head_commit": head, "checked_at": checked_at}

        with self._lock:
            self._cache[key] = dict(result)
        return result
