from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.job_lock import JobLock


STALE_LOCK_MINUTES = 60


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

    if lock.started_at is None:
        return True

    return datetime.utcnow() - lock.started_at > timedelta(minutes=STALE_LOCK_MINUTES)


def try_acquire_job_lock(db: Session, job_name: str) -> bool:
    lock = get_or_create_job_lock(db, job_name)

    if lock.is_running and not _is_stale(lock):
        return False

    lock.is_running = True
    lock.started_at = datetime.utcnow()
    db.commit()
    return True


def release_job_lock(db: Session, job_name: str) -> None:
    lock = get_or_create_job_lock(db, job_name)
    lock.is_running = False
    lock.started_at = None
    db.commit()