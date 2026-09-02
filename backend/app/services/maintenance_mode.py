"""Process-wide maintenance switch, used by the Postgres migration.

While the migration copies data, anything that writes to SQLite would silently
miss the move — so mutating requests are refused with an honest 503 instead.
During the brief cutover-to-restart window everything except health and the
migration progress poll is refused, so nothing can touch the retired database.
"""

import threading

MODE_MIGRATION = "migration"
MODE_RESTARTING = "restarting"

_guard = threading.Lock()
_mode: str | None = None

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Auth must keep working (people signing in mid-migration is fine — sessions
# are reads plus a cookie), and the migration's own status/progress endpoints
# are how the UI watches the job it started.
_ALLOWED_PREFIXES = (
    "/api/health",
    "/api/auth",
    "/api/settings/database",
)


def enable_migration() -> None:
    global _mode
    with _guard:
        _mode = MODE_MIGRATION


def enable_restarting() -> None:
    global _mode
    with _guard:
        _mode = MODE_RESTARTING


def clear() -> None:
    global _mode
    with _guard:
        _mode = None


def current() -> str | None:
    with _guard:
        return _mode


def blocks(method: str, path: str) -> bool:
    mode = current()

    if mode is None:
        return False

    if path.startswith("/api/health"):
        return False

    if mode == MODE_RESTARTING:
        # The progress poll is answered straight from the middleware (module
        # state only — an auth check here would touch the retired database).
        return not path.startswith("/api/settings/database/migration")

    if method not in _WRITE_METHODS:
        return False

    return not any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)
