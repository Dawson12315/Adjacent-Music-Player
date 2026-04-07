from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.maintenance import cleanup_missing_tracks

router = APIRouter()


@router.post("/maintenance/cleanup", tags=["maintenance"])
def run_cleanup(db: Session = Depends(get_db)):
    if not try_acquire_job_lock(db, "cleanup"):
        return {
            "message": "Cleanup already running",
            "removed": 0,
        }

    try:
        result = cleanup_missing_tracks(db)
        return {
            "message": "Cleanup completed",
            "removed": result["removed"],
        }
    finally:
        release_job_lock(db, "cleanup")