"""Client-side token-bucket limiter matching the Week 4 Gateway budget."""

from __future__ import annotations

import time
from threading import Lock
from typing import Callable


class ToolRateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 30,
        burst: int = 5,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if requests_per_minute <= 0 or burst <= 0:
            raise ValueError("Rate and burst must be positive")
        self._rate_per_second = requests_per_minute / 60.0
        self._capacity = float(burst)
        self._tokens = float(burst)
        self._clock = clock
        self._sleeper = sleeper
        self._updated_at = clock()
        self._lock = Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = self._clock()
                elapsed = max(0.0, now - self._updated_at)
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_second)
                self._updated_at = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                delay = (1.0 - self._tokens) / self._rate_per_second
            self._sleeper(delay)
