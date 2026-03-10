"""
utils/rate_limiter.py
─────────────────────
Token-bucket rate limiter for controlling API call frequency.

Usage:
    limiter = RateLimiter(calls_per_second=1.0)
    for item in items:
        await limiter.acquire()   # async version
        # ... or ...
        limiter.acquire_sync()    # sync version
        call_api(item)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """
    Thread-safe token-bucket rate limiter.

    Parameters
    ----------
    calls_per_second: Target rate (can be < 1 for per-minute rates, e.g. 50/60 ≈ 0.83).
    burst:            Max tokens accumulated while idle (defaults to calls_per_second).
    """

    calls_per_second: float
    burst: float = field(default=0.0)

    _tokens: float = field(init=False, default=0.0)
    _last_refill: float = field(init=False, default=0.0)
    _lock: Lock = field(init=False, default_factory=Lock)

    def __post_init__(self) -> None:
        if self.calls_per_second <= 0:
            raise ValueError("calls_per_second must be > 0")
        if self.burst == 0.0:
            self.burst = self.calls_per_second
        self._tokens = self.burst
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.calls_per_second)
        self._last_refill = now

    def acquire_sync(self) -> None:
        """Block the calling thread until a token is available."""
        with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                sleep_for = (1.0 - self._tokens) / self.calls_per_second
        time.sleep(sleep_for)

    async def acquire(self) -> None:
        """Async version — yields control to the event loop while waiting."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                sleep_for = (1.0 - self._tokens) / self.calls_per_second
            await asyncio.sleep(sleep_for)


# ── Convenience pre-built limiters ────────────────────────────────────────────

def apollo_limiter() -> RateLimiter:
    """Apollo free tier: ~50 req/month → treat as 1 req/second burst."""
    return RateLimiter(calls_per_second=1.0)


def gemini_limiter() -> RateLimiter:
    """Gemini free tier: 15 RPM = 0.25 req/second."""
    return RateLimiter(calls_per_second=0.25)


def instantly_limiter() -> RateLimiter:
    """Instantly.ai: 2 req/second."""
    return RateLimiter(calls_per_second=2.0)


def similarweb_limiter() -> RateLimiter:
    """Similarweb: 1 req/second."""
    return RateLimiter(calls_per_second=1.0)
