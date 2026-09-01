"""Process-level caches for recommendation building blocks.

The heavy per-request costs were rebuilding the same library-wide structures
on every call: the artist-name lookup, the artist→tracks map, and the
genre→family map. All three only change when the library changes, so they are
cached here and invalidated by the events that change the library (scan
completion, cleanup, purge, track edits).

Single-process by design — the app runs as one uvicorn process. A TTL bounds
staleness even if an invalidation hook is ever missed.
"""

import threading
import time
from typing import Any, Callable

_CACHE_TTL_SECONDS = 15 * 60

_guard = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


def get_or_build(key: str, builder: Callable[[], Any]) -> Any:
    now = time.monotonic()

    with _guard:
        entry = _cache.get(key)
        if entry and entry[0] > now:
            return entry[1]

    value = builder()

    with _guard:
        _cache[key] = (now + _CACHE_TTL_SECONDS, value)

    return value


def invalidate_library_caches() -> None:
    """Call after anything that adds, removes, or edits tracks."""
    with _guard:
        _cache.clear()
