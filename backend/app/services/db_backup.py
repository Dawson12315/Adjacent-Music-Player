"""Consistent copies of the SQLite database.

Copying `app.db` while the server runs is not a backup: in WAL mode the last
few hours of likes, plays and playlist edits may only exist in `app.db-wal`,
and a file copier can catch the main file mid-checkpoint. SQLite's online
backup API produces a single self-contained file that opens anywhere, so a
nightly one lands next to the database where any existing "copy the data
directory" habit picks it up.

Postgres installs are not covered here — `pg_dump` is the tool for those, and
the README says how.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db import engine

logger = logging.getLogger(__name__)

BACKUP_DIRECTORY_NAME = "backups"
NIGHTLY_LABEL = "nightly"
NIGHTLY_KEEP = 7


def sqlite_database_path() -> Path | None:
    if engine.dialect.name != "sqlite":
        return None

    database = engine.url.database
    if not database or database == ":memory:":
        return None

    return Path(database)


def backup_directory() -> Path | None:
    database = sqlite_database_path()
    if database is None:
        return None
    return database.parent / BACKUP_DIRECTORY_NAME


def backup_sqlite_database(label: str = NIGHTLY_LABEL, keep: int = NIGHTLY_KEEP) -> Path | None:
    """Write `backups/app-<label>-<stamp>.db` and keep the newest `keep`.

    Returns the path written, or None when the install is not on SQLite.
    Raises on failure — a caller about to delete data must know the safety
    copy did not happen.
    """
    database = sqlite_database_path()
    if database is None:
        return None

    directory = database.parent / BACKUP_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    destination = directory / f"{database.stem}-{label}-{stamp}.db"
    serial = 1
    while destination.exists():
        serial += 1
        destination = directory / f"{database.stem}-{label}-{stamp}-{serial}.db"
    partial = destination.with_name(destination.name + ".part")
    partial.unlink(missing_ok=True)

    raw = engine.raw_connection()
    try:
        source = raw.driver_connection
        target = sqlite3.connect(str(partial))
        try:
            # The online backup API copies pages under SQLite's own locking,
            # so the result is a consistent snapshot even mid-write.
            source.backup(target)
        finally:
            target.close()
    finally:
        raw.close()

    partial.replace(destination)
    _rotate(directory, f"{database.stem}-{label}-", keep)

    logger.info("Database backup written to %s", destination)
    return destination


def _rotate(directory: Path, prefix: str, keep: int) -> None:
    candidates = sorted(
        path for path in directory.glob(f"{prefix}*.db") if path.is_file()
    )

    for stale in candidates[:-keep] if keep > 0 else candidates:
        try:
            stale.unlink()
        except OSError:
            logger.warning("Could not remove old backup %s", stale, exc_info=True)


def run_nightly_backup() -> None:
    try:
        written = backup_sqlite_database()
        if written is None:
            logger.debug("Nightly backup skipped: not on SQLite")
    except Exception:  # noqa: BLE001 — logged, never fatal to the scheduler
        logger.exception("Nightly database backup failed")
