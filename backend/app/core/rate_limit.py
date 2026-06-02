"""Simple in-process sliding-window rate limiter (per user, per endpoint key)."""
import threading
from collections import deque
from datetime import datetime, timedelta

_windows: dict[str, deque] = {}
_lock = threading.Lock()


def is_rate_limited(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Return True if *key* has exceeded *limit* calls in the last *window_seconds*."""
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    with _lock:
        q = _windows.setdefault(key, deque())
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False
