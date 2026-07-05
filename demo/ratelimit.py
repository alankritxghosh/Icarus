# demo/ratelimit.py
"""Per-key sliding-window rate limiter. Ingest shells out to git/gh and the
writer bills per request — bound both per identity. Stdlib, thread-safe."""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: float, _now=time.time):
        self._limit, self._window = limit, window
        self._now = _now  # injectable for deterministic tests; defaults to real time
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._now()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self._window:
                q.popleft()
            if len(q) >= self._limit:
                return False
            q.append(now)
            return True
