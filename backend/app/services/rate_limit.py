"""In-memory failure rate limiting for credential endpoints.

Adjacent runs as a single process on a single host, so a process-local sliding
window is enough to stop online brute force against login and recovery codes.
State intentionally lives in memory: restarting the server clears it, and
nothing here needs to survive a restart.
"""

import threading
import time

# Hard ceiling on tracked keys so an attacker rotating usernames cannot grow
# the dict without bound. When hit, the oldest windows are dropped first.
_MAX_TRACKED_KEYS = 10_000


class FailureRateLimiter:
    """Sliding-window limiter counting *failures* per key.

    Successful attempts clear the key, so legitimate users only ever hit the
    limit after `max_failures` consecutive bad tries inside the window.
    """

    def __init__(self, max_failures: int, window_seconds: int):
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def retry_after_seconds(self, key: str) -> int:
        """Seconds until the key may try again; 0 when not blocked."""
        now = time.monotonic()

        with self._lock:
            timestamps = self._prune_key(key, now)

            if len(timestamps) < self._max_failures:
                return 0

            oldest_in_window = timestamps[0]
            return max(1, int(oldest_in_window + self._window_seconds - now) + 1)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()

        with self._lock:
            if key not in self._failures and len(self._failures) >= _MAX_TRACKED_KEYS:
                self._evict_oldest(now)

            timestamps = self._prune_key(key, now)
            timestamps.append(now)
            self._failures[key] = timestamps

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _prune_key(self, key: str, now: float) -> list[float]:
        cutoff = now - self._window_seconds
        timestamps = [moment for moment in self._failures.get(key, []) if moment > cutoff]

        if timestamps:
            self._failures[key] = timestamps
        else:
            self._failures.pop(key, None)

        return timestamps

    def _evict_oldest(self, now: float) -> None:
        cutoff = now - self._window_seconds

        for key in list(self._failures):
            timestamps = [moment for moment in self._failures[key] if moment > cutoff]

            if timestamps:
                self._failures[key] = timestamps
            else:
                del self._failures[key]

        # Still full after pruning expired windows: drop the stalest keys.
        if len(self._failures) >= _MAX_TRACKED_KEYS:
            stalest = sorted(self._failures, key=lambda k: self._failures[k][-1])
            for key in stalest[: _MAX_TRACKED_KEYS // 10]:
                del self._failures[key]


# 10 bad passwords in 15 minutes per (client, username) before a cool-down.
login_limiter = FailureRateLimiter(max_failures=10, window_seconds=15 * 60)

# Recovery codes are short, so the window is tighter.
recovery_limiter = FailureRateLimiter(max_failures=5, window_seconds=15 * 60)

# Second tier, keyed on the username alone. The per-client limiters above are
# the primary defence, but they can be sidestepped by an attacker rotating
# source addresses (trivial on IPv6) — and they collapse into a single shared
# bucket if the app sits behind a proxy without forwarded-header trust
# configured. This ceiling is set far above anything a real person types, so
# it only ever engages under sustained attack, and it is checked *after* the
# per-client tier so a normal user's mistyping never reaches it.
username_login_limiter = FailureRateLimiter(max_failures=50, window_seconds=60 * 60)
