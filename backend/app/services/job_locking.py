"""Database-backed mutual exclusion for background jobs.

Jobs run in this process's threads, so a lock can only be orphaned by a crash
or a reload — both of which `release_all_job_locks` clears at boot. The stale
rule below is the safety net for a job that hangs without dying: it is
measured from the job's last heartbeat, so a scan that legitimately runs for
hours keeps its lock as long as it keeps making progress.
"""

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.job_lock import JobLock
from app.services import maintenance_mode

logger = logging.getLogger(__name__)

# A job that has not heartbeat in this long is presumed hung. Every long job
# ticks its heartbeat far more often than this (see JobHeartbeat).
STALE_LOCK_MINUTES = 10

# The migration is the one job allowed to start while writes are paused —
# it is the job doing the pausing.
_MIGRATION_JOB_NAME = "pg_migration"


def get_or_create_job_lock(db: Session, job_name: str) -> JobLock:
    lock = db.query(JobLock).filter(JobLock.job_name == job_name).first()

    if lock:
        return lock

    lock = JobLock(job_name=job_name, is_running=False, started_at=None)
    db.add(lock)
    db.commit()
    db.refresh(lock)
    return lock


def _is_stale(lock: JobLock) -> bool:
    if not lock.is_running:
        return False

    last_seen = lock.heartbeat_at or lock.started_at
    if last_seen is None:
        return True

    return datetime.utcnow() - last_seen > timedelta(minutes=STALE_LOCK_MINUTES)


def try_acquire_job_lock(db: Session, job_name: str) -> bool:
    # While the Postgres migration copies SQLite, any job that starts would
    # write rows the copy never sees. Refusing here covers every job at once,
    # scheduled or manual, without each of them having to remember.
    if job_name != _MIGRATION_JOB_NAME and maintenance_mode.writes_paused():
        logger.info("Job %s not started: database migration in progress", job_name)
        return False

    lock = get_or_create_job_lock(db, job_name)

    if lock.is_running and not _is_stale(lock):
        return False

    if lock.is_running:
        logger.warning(
            "Job lock %s looked hung (no heartbeat since %s); taking it over",
            job_name,
            lock.heartbeat_at or lock.started_at,
        )

    now = datetime.utcnow()
    lock.is_running = True
    lock.started_at = now
    lock.heartbeat_at = now
    db.commit()
    return True


def release_job_lock(db: Session, job_name: str) -> None:
    lock = get_or_create_job_lock(db, job_name)
    lock.is_running = False
    lock.started_at = None
    lock.heartbeat_at = None
    db.commit()


def heartbeat_job_lock(job_name: str) -> None:
    """Record that the job holding this lock is still making progress.

    Uses its own short session so it never entangles with whatever
    transaction the job itself has open.
    """
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        lock = db.query(JobLock).filter(JobLock.job_name == job_name).first()
        if lock is not None and lock.is_running:
            lock.heartbeat_at = datetime.utcnow()
            db.commit()
    except Exception:  # noqa: BLE001 — a missed heartbeat must never stop the job
        logger.debug("Heartbeat for %s failed", job_name, exc_info=True)
        db.rollback()
    finally:
        db.close()


class JobHeartbeat:
    """Call `tick()` from inside a job's loop; it writes at most once per
    `interval_seconds`, so ticking per file or per row costs nothing."""

    def __init__(self, job_name: str, interval_seconds: float = 60.0):
        self.job_name = job_name
        self.interval_seconds = interval_seconds
        self._last = time.monotonic()

    def tick(self) -> None:
        now = time.monotonic()
        if now - self._last < self.interval_seconds:
            return
        self._last = now
        heartbeat_job_lock(self.job_name)


def release_all_job_locks() -> None:
    """Called at startup. Jobs run in this process's threads, so a fresh boot
    cannot have any running job — anything still marked running is a lock
    orphaned by a crash, a reload, or Ctrl+C mid-job."""
    from app.db import SessionLocal

    db = SessionLocal()

    try:
        db.query(JobLock).update(
            {
                JobLock.is_running: False,
                JobLock.started_at: None,
                JobLock.heartbeat_at: None,
            },
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()
