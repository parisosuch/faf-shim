"""In-memory fixed-window rate limiter, keyed by shim slug."""

import time
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class _Window:
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


_windows: dict[str, _Window] = defaultdict(lambda: _Window(window_start=0))


def is_allowed(slug: str, limit: int, window_seconds: int) -> bool:
    """Return True if the request is within the rate limit, False otherwise.

    Uses a fixed window: the counter resets whenever more than window_seconds
    have elapsed since the window started.
    """
    now = time.monotonic()
    w = _windows[slug]
    if now - w.window_start >= window_seconds:
        w.count = 1
        w.window_start = now
        return True
    w.count += 1
    return w.count <= limit


def clear() -> None:
    """Reset all window state — used in tests."""
    _windows.clear()
