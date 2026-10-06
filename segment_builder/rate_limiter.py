"""A sliding-window rate limiter, used to keep the vendor write-back client
inside the vendor's documented budget (100 requests per rolling 10 seconds,
the Quickbase REST API limit: see README). Time and sleep are injected so the
pacing algorithm itself can be proven correct in a fast, deterministic unit
test (tests/test_rate_limiter.py) without a real clock, while production code
uses the real one by default.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import time as _time_module


@dataclass
class SlidingWindowRateLimiter:
    max_requests: int
    window_seconds: float
    time_fn: Callable[[], float] = _time_module.monotonic
    sleep_fn: Callable[[float], None] = _time_module.sleep
    # A client that paces itself to the exact edge of its own window races the
    # remote side's window, which is anchored to receipt time rather than
    # send time: see README Findings ("the 101st request race"). This client
    # was measured sending its 101st request at its own t=10.000s while the
    # server's window (anchored ~2ms later than the client's own first
    # timestamp, the first request's one-way network delay) had not yet
    # evicted its oldest entry, producing a real, reproducible 429 at exactly
    # the 100-request boundary. The fix is this fixed safety margin, not a
    # larger window or a smaller budget.
    safety_margin_seconds: float = 0.25
    _timestamps: deque[float] = field(default_factory=deque, init=False)

    def acquire(self) -> float:
        """Blocks until sending one more request would not push the trailing
        window over `max_requests`, records that send, and returns the total
        time spent waiting (0.0 if no wait was needed)."""
        waited = 0.0
        while True:
            now = self.time_fn()
            self._evict_expired(now)
            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return waited
            sleep_for = max(
                self.window_seconds - (now - self._timestamps[0]) + self.safety_margin_seconds, 1e-4
            )
            self.sleep_fn(sleep_for)
            waited += sleep_for

    def _evict_expired(self, now: float) -> None:
        while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
            self._timestamps.popleft()

    def requests_in_window(self, now: float | None = None) -> int:
        now = self.time_fn() if now is None else now
        self._evict_expired(now)
        return len(self._timestamps)

    def try_acquire(self) -> bool:
        """Non-blocking variant for a server deciding whether to accept a
        request right now: records and returns True if under budget,
        otherwise returns False (and records nothing) without sleeping."""
        now = self.time_fn()
        self._evict_expired(now)
        if len(self._timestamps) >= self.max_requests:
            return False
        self._timestamps.append(now)
        return True
