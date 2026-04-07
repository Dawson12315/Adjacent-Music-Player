from sqlalchemy.orm import Session

from app.models.job_lock import JobLock


def get_or_create_job_lock(db: Session, job_name: str) -> JobLock:
    lock = db.query(JobLock).filter(JobLock.job_name == job_name).first()

    if lock:
        return lock

    lock = JobLock(job_name=job_name, is_running=False)
    db.add(lock)
    db.commit()
    db.refresh(lock)
    return lock


def try_acquire_job_lock(db: Session, job_name: str) -> bool:
    lock = get_or_create_job_lock(db, job_name)

    if lock.is_running:
        return False

    lock.is_running = True
    db.commit()
    return True


def release_job_lock(db: Session, job_name: str) -> None:
    lock = get_or_create_job_lock(db, job_name)
    lock.is_running = False
    db.commit()