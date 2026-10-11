"""In-memory rate limiter protecting GraphSupport AI resources (Phase 7).

Implements a thread-safe sliding-window request throttling mechanism per client or
customer session. Prevents resource exhaustion, quota abuse, and automated scraping.
"""

import threading
import time
from collections import defaultdict

from graphsupport.core.exceptions import RateLimitExceededError


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter per identity key."""

    def __init__(self, max_requests_per_minute: int = 60, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests_per_minute
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, key: str) -> bool:
        """Check if request for key is permitted under current sliding window.

        Args:
            key: Rate limit partition identifier (e.g., customer_id or session_id).

        Returns:
            True if permitted, False if limit exceeded.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Clean expired timestamps
            valid_timestamps = [t for t in self._timestamps[key] if t > cutoff]
            if len(valid_timestamps) >= self.max_requests:
                self._timestamps[key] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._timestamps[key] = valid_timestamps
            return True

    def enforce_rate_limit(self, key: str) -> None:
        """Verify request limit for key, raising RateLimitExceededError if violated.

        Args:
            key: Rate limit partition identifier.

        Raises:
            RateLimitExceededError: If request rate exceeds configured threshold.
        """
        if not self.check_rate_limit(key):
            remaining_seconds = int(self.window_seconds)
            raise RateLimitExceededError(
                f"Rate limit of {self.max_requests} requests per {remaining_seconds}s "
                f"exceeded for key '{key}'. Please wait before submitting additional requests."
            )

    def get_remaining_requests(self, key: str) -> int:
        """Get remaining allowed requests for key in current window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            valid_timestamps = [t for t in self._timestamps[key] if t > cutoff]
            self._timestamps[key] = valid_timestamps
            return max(0, self.max_requests - len(valid_timestamps))

    def reset(self, key: str | None = None) -> None:
        """Reset history for a specific key or all keys (useful for test isolation)."""
        with self._lock:
            if key is not None:
                self._timestamps.pop(key, None)
            else:
                self._timestamps.clear()


# Global default limiter instance configured for support sessions
_global_rate_limiter = InMemoryRateLimiter(max_requests_per_minute=60, window_seconds=60.0)


def get_rate_limiter() -> InMemoryRateLimiter:
    """Obtain default application rate limiter singleton."""
    return _global_rate_limiter
