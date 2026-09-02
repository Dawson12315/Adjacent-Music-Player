"""SQLite → PostgreSQL migration engine.

Design rules, in order of importance:

1. SQLite is only ever READ — and only through a point-in-time snapshot
   (VACUUM INTO), so a failure at any step before cutover leaves the install
   exactly as it was. The live file is retired to a backup name on the first
   boot after cutover, never during the run.
2. "Copied" is a claim; the verify step demands row-count parity plus id
   checksums per table before the cutover config is written.
3. On any error the partially-built Postgres schema is dropped, so the next
   attempt starts clean instead of tripping over leftovers.

Runs as a daemon thread with module-level progress state, the same shape the
library scan uses.
"""

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, func, inspect, select, text

from app.config import RUNTIME_DATABASE_CONFIG_PATH, settings
from app.db import Base, SessionLocal
from app.db import engine as live_engine
from app.models.job_lock import JobLock
from app.services import maintenance_mode
from app.services.job_locking import release_job_lock, try_acquire_job_lock

logger = logging.getLogger(__name__)

COPY_BATCH_SIZE = 5_000
MINIMUM_POSTGRES_MAJOR = 13
JOB_NAME = "pg_migration"

SNAPSHOT_PATH = Path("data/migration-snapshot.db")

# Rows in these tables are process-transient; the new database starts them fresh.
SKIP_DATA_TABLES = {"job_locks"}

# Rows with a NULL user_id predate authentication; they belong to the admin.
USER_BACKFILL_TABLES = {
    "playlists",
    "listening_events",
    "track_user_stats",
    "playback_sessions",
}

_runner_guard = threading.Lock()
_migration_thread: threading.Thread | None = None

_progress_guard = threading.Lock()
_progress = {
    "state": "idle",  # idle | running | restarting | failed
    "step": None,     # snapshot | schema | copy | verify | cutover
    "table": None,
    "tables_done": 0,
    "tables_total": 0,
    "rows_done": 0,
    "rows_total": 0,
    "error": None,
    "started_at": None,
    "finished_at": None,
}


def _update(**changes):
    with _progress_guard:
        _progress.update(changes)


def get_migration_progress() -> dict:
    with _progress_guard:
        return dict(_progress)


def build_postgres_url(params) -> str:
    auth = quote_plus(params.username)
    if params.password:
        auth += ":" + quote_plus(params.password)

    url = (
        f"postgresql+psycopg://{auth}@{params.host}:{params.port}"
        f"/{quote_plus(params.database)}"
    )

    if params.sslmode:
        url += f"?sslmode={quote_plus(params.sslmode)}"

    return url


def mask_database_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url

    scheme, rest = url.split("://", 1)
    auth, host = rest.rsplit("@", 1)

    if ":" in auth:
        auth = auth.split(":", 1)[0] + ":•••"

    return f"{scheme}://{auth}@{host}"


def _friendly_connection_error(error: Exception, params) -> str:
    cause = getattr(error, "orig", None) or error
    message = str(cause).strip().splitlines()[0] if str(cause).strip() else "connection failed"

    lowered = message.lower()
    if "connection refused" in lowered:
        return (
            f"Connection refused — is Postgres running on "
            f"{params.host}:{params.port}?"
        )
    if "password authentication failed" in lowered:
        return f"Password authentication failed for user “{params.username}”."
    if "does not exist" in lowered and "database" in lowered:
        return f"Database “{params.database}” does not exist on that server."
    if "timeout" in lowered or "timed out" in lowered:
        return f"Timed out reaching {params.host}:{params.port}."

    return message


def _inspect_target_state(pg_engine) -> str:
    """empty | leftover_adjacent | occupied"""
    existing = set(inspect(pg_engine).get_table_names())

    if not existing:
        return "empty"

    ours = {table.name for table in Base.metadata.sorted_tables}
    if existing <= ours:
        return "leftover_adjacent"

    return "occupied"


def test_connection(params) -> dict:
    """Reach the server, read its version, and classify the target database."""
    url = build_postgres_url(params)
    probe = create_engine(url, connect_args={"connect_timeout": 5})

    try:
        with probe.connect() as connection:
            version = connection.execute(text("SHOW server_version")).scalar() or ""

        target_state = _inspect_target_state(probe)
    except Exception as error:  # noqa: BLE001 — every driver failure becomes one message
        return {"ok": False, "error": _friendly_connection_error(error, params)}
    finally:
        probe.dispose()

    try:
        major = int(str(version).split(".")[0])
    except ValueError:
        major = 0

    if major and major < MINIMUM_POSTGRES_MAJOR:
        return {
            "ok": False,
            "error": (
                f"PostgreSQL {version} is too old — "
                f"{MINIMUM_POSTGRES_MAJOR} or newer is required."
            ),
        }

    if target_state == "occupied":
        return {
            "ok": False,
            "error": (
                f"Database “{params.database}” already contains tables that are "
                "not Adjacent's. Point at an empty database."
            ),
        }

    return {"ok": True, "server_version": str(version), "target_state": target_state}


def _other_job_running() -> str | None:
    db = SessionLocal()
    try:
        running = (
            db.query(JobLock)
            .filter(JobLock.is_running.is_(True), JobLock.job_name != JOB_NAME)
            .first()
        )
        return running.job_name if running else None
    finally:
        db.close()


def start_migration_background(params) -> dict:
    """Returns {"started": bool, "reason": str}."""
    global _migration_thread

    if live_engine.dialect.name != "sqlite":
        return {"started": False, "reason": "already_postgres"}

    with _runner_guard:
        if _migration_thread is not None and _migration_thread.is_alive():
            return {"started": False, "reason": "already_running"}

        other_job = _other_job_running()
        if other_job:
            return {"started": False, "reason": f"job_running:{other_job}"}

        db = SessionLocal()
        try:
            if not try_acquire_job_lock(db, JOB_NAME):
                return {"started": False, "reason": "already_running"}
        finally:
            db.close()

        _update(
            state="running",
            step=None,
            table=None,
            tables_done=0,
            tables_total=0,
            rows_done=0,
            rows_total=0,
            error=None,
            started_at=time.time(),
            finished_at=None,
        )

        _migration_thread = threading.Thread(
            target=_run_migration,
            args=(params,),
            name="pg-migration",
            daemon=True,
        )
        _migration_thread.start()

    return {"started": True, "reason": "started"}


def _run_migration(params):
    pg_url = build_postgres_url(params)
    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    snap_engine = None

    try:
        maintenance_mode.enable_migration()

        _update(step="snapshot")
        _make_snapshot()
        snap_engine = create_engine(f"sqlite:///{SNAPSHOT_PATH.as_posix()}")

        _update(step="schema")
        _prepare_target_schema(pg_engine)

        _update(step="copy")
        _copy_all_tables(snap_engine, pg_engine)

        _update(step="verify")
        _verify(snap_engine, pg_engine)
        _reset_sequences(pg_engine)

        _update(step="cutover")
        _write_cutover_config(pg_url)

        logger.info("Postgres migration verified and cut over; restarting")
        maintenance_mode.enable_restarting()
        _update(state="restarting", finished_at=time.time())
        _schedule_restart()

    except Exception as error:  # noqa: BLE001 — surfaced to the UI verbatim
        logger.exception("Postgres migration failed")
        _wipe_partial_target(pg_engine)
        maintenance_mode.clear()
        _update(
            state="failed",
            error=str(error),
            finished_at=time.time(),
        )

        db = SessionLocal()
        try:
            release_job_lock(db, JOB_NAME)
        finally:
            db.close()

    finally:
        if snap_engine is not None:
            snap_engine.dispose()
        pg_engine.dispose()
        SNAPSHOT_PATH.unlink(missing_ok=True)


def _make_snapshot():
    SNAPSHOT_PATH.unlink(missing_ok=True)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # VACUUM refuses to run inside a transaction; AUTOCOMMIT bypasses the
    # connection's implicit begin. The path contains no quotes — it is ours.
    with live_engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        connection.exec_driver_sql(f"VACUUM INTO '{SNAPSHOT_PATH.as_posix()}'")


def _prepare_target_schema(pg_engine):
    state = _inspect_target_state(pg_engine)

    if state == "occupied":
        raise RuntimeError(
            "Target database contains tables that are not Adjacent's — refusing "
            "to touch it."
        )

    if state == "leftover_adjacent":
        logger.info("Dropping leftover Adjacent schema from a previous attempt")
        Base.metadata.drop_all(bind=pg_engine)

    Base.metadata.create_all(bind=pg_engine)


def _find_admin_id(snap_engine) -> int | None:
    users = Base.metadata.tables["users"]

    with snap_engine.connect() as connection:
        row = connection.execute(
            select(users.c.id)
            .where(users.c.role == "admin")
            .order_by(users.c.id)
            .limit(1)
        ).first()

    return row[0] if row else None


def _copy_all_tables(snap_engine, pg_engine):
    tables = list(Base.metadata.sorted_tables)
    admin_id = _find_admin_id(snap_engine)

    totals = {}
    with snap_engine.connect() as connection:
        for table in tables:
            if table.name in SKIP_DATA_TABLES:
                totals[table.name] = 0
                continue
            totals[table.name] = connection.execute(
                select(func.count()).select_from(table)
            ).scalar()

    _update(tables_total=len(tables), rows_total=sum(totals.values()))

    rows_done = 0
    tables_done = 0

    for table in tables:
        _update(table=table.name)

        if table.name in SKIP_DATA_TABLES or totals[table.name] == 0:
            tables_done += 1
            _update(tables_done=tables_done)
            continue

        backfill_user = table.name in USER_BACKFILL_TABLES and admin_id is not None

        with snap_engine.connect() as source, pg_engine.begin() as target:
            result = source.execution_options(yield_per=COPY_BATCH_SIZE).execute(
                select(table)
            )

            for batch in result.mappings().partitions(COPY_BATCH_SIZE):
                rows = [dict(row) for row in batch]

                if backfill_user:
                    for row in rows:
                        if row.get("user_id") is None:
                            row["user_id"] = admin_id

                target.execute(table.insert(), rows)
                rows_done += len(rows)
                _update(rows_done=rows_done)

        tables_done += 1
        _update(tables_done=tables_done)
        logger.info(
            "Copied %s: %s rows (%s/%s tables)",
            table.name,
            totals[table.name],
            tables_done,
            len(tables),
        )


def _verify(snap_engine, pg_engine):
    tables = list(Base.metadata.sorted_tables)

    with snap_engine.connect() as source, pg_engine.connect() as target:
        for table in tables:
            if table.name in SKIP_DATA_TABLES:
                continue

            source_count = source.execute(
                select(func.count()).select_from(table)
            ).scalar()
            target_count = target.execute(
                select(func.count()).select_from(table)
            ).scalar()

            if source_count != target_count:
                raise RuntimeError(
                    f"Verification failed: {table.name} has {source_count} rows "
                    f"on SQLite but {target_count} on Postgres."
                )

            if "id" in table.c:
                checksum = select(func.coalesce(func.sum(table.c.id), 0)).select_from(
                    table
                )
                source_sum = source.execute(checksum).scalar()
                target_sum = target.execute(checksum).scalar()

                if source_sum != target_sum:
                    raise RuntimeError(
                        f"Verification failed: {table.name} id checksum mismatch."
                    )

    logger.info("Verification passed: all tables match")


def _reset_sequences(pg_engine):
    """Without this, the first insert after migration collides with a copied id."""
    with pg_engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if "id" not in table.c or not table.c.id.primary_key:
                continue

            max_id = connection.execute(select(func.max(table.c.id))).scalar()
            if max_id:
                connection.execute(
                    text("SELECT setval(pg_get_serial_sequence(:table, 'id'), :max_id)"),
                    {"table": table.name, "max_id": max_id},
                )


def _wipe_partial_target(pg_engine):
    """A failed attempt must not leave debris for the next one to trip over."""
    try:
        if _inspect_target_state(pg_engine) == "leftover_adjacent":
            Base.metadata.drop_all(bind=pg_engine)
            logger.info("Wiped partial Postgres schema after failure")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not wipe the partial Postgres schema; the next attempt "
            "will clear it during preflight",
            exc_info=True,
        )


def _write_cutover_config(pg_url: str):
    RUNTIME_DATABASE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_DATABASE_CONFIG_PATH.write_text(
        json.dumps(
            {
                "database_url": pg_url,
                "engine": "postgresql",
                "migrated_at": datetime.utcnow().isoformat() + "Z",
                "legacy_sqlite": _sqlite_file_path(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(RUNTIME_DATABASE_CONFIG_PATH, 0o600)


def _sqlite_file_path() -> str:
    return settings.database_url.replace("sqlite:///", "", 1)


def _schedule_restart():
    """Exit cleanly after the progress poller has had a moment to see
    "restarting". Docker's restart policy boots us back up on Postgres; bare
    installs see the UI's "restart the server to finish" fallback."""

    def _exit():
        time.sleep(1.5)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_exit, name="pg-migration-restart", daemon=True).start()


def retire_legacy_sqlite_file():
    """First boot on Postgres: move the old SQLite files to backup names.

    Done here, not at cutover — while the old process is still winding down,
    any stray connection would recreate an empty app.db and make it look like
    data loss. After the restart nothing can touch it.
    """
    if live_engine.dialect.name != "postgresql":
        return

    # Only a real cutover leaves database.json behind. An install pointed at
    # Postgres directly (CI, a fresh deploy with DATABASE_URL set by hand)
    # never migrated, so any SQLite file lying around is not ours to touch.
    try:
        recorded = json.loads(
            RUNTIME_DATABASE_CONFIG_PATH.read_text(encoding="utf-8")
        ).get("legacy_sqlite")
    except (OSError, ValueError):
        return

    if not isinstance(recorded, str) or not recorded:
        return

    legacy = Path(recorded)
    if not legacy.exists():
        return

    backup = legacy.with_name(legacy.name + ".pre-postgres")
    if backup.exists():
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup = legacy.with_name(f"{legacy.name}.pre-postgres.{stamp}")

    legacy.rename(backup)

    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{legacy}{suffix}")
        if sidecar.exists():
            sidecar.rename(Path(f"{backup}{suffix}"))

    logger.info("Retired legacy SQLite database to %s", backup)
