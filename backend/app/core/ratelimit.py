"""Tiny in-memory sliding-window rate limiter (per client key). Enough for a single-process lab server."""
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, max_keys: int = 10_000, clock=time.monotonic):
        self.limit, self.window, self.max_keys, self.clock = limit, window_seconds, max_keys, clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            if key not in self._hits and len(self._hits) >= self.max_keys:
                for k in [k for k, d in self._hits.items() if not d or now - d[-1] > self.window][: self.max_keys // 10 + 1]:
                    del self._hits[k]
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True
