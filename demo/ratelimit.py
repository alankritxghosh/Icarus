# demo/ratelimit.py
"""Per-key sliding-window rate limiter. Ingest shells out to git/gh and the
writer bills per request — bound both per identity. Stdlib, thread-safe."""

import threading
import time
from math import ceil
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: float, _now=time.time):
        if limit <= 0 or window <= 0:
            raise ValueError("rate-limit limit and window must be positive")
        self._limit, self._window = limit, window
        self._now = _now  # injectable for deterministic tests; defaults to real time
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, q, now):
        while q and q[0] <= now - self._window:
            q.popleft()

    def allow(self, key: str) -> bool:
        now = self._now()
        with self._lock:
            q = self._hits[key]
            self._prune(q, now)
            if len(q) >= self._limit:
                return False
            q.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Whole seconds until ``key`` can spend one request, or zero now.

        Reading this value never consumes budget. ``ceil`` prevents a client
        from retrying fractionally before the sliding window has actually
        released its oldest request.
        """
        now = self._now()
        with self._lock:
            q = self._hits[key]
            self._prune(q, now)
            if len(q) < self._limit:
                return 0
            return max(1, ceil(q[0] + self._window - now))
