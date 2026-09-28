from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.maintenance import (
    CleanupRefused,
    LibraryUnavailable,
    cleanup_missing_tracks,
)

router = APIRouter()


@router.post("/maintenance/cleanup", tags=["maintenance"])
def run_cleanup(
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove tracks whose files are gone.

    Without `force`, a track is only removed once it has been missing for the
    grace period, and never more than the safety threshold in one go — the
    409 carries the counts so the UI can ask before retrying with `force`.
    """
    if not try_acquire_job_lock(db, "cleanup"):
        return {
            "message": "Cleanup already running",
            "removed": 0,
            "marked_missing": 0,
            "still_missing": 0,
            "returned": 0,
        }

    try:
        result = cleanup_missing_tracks(db, force=force)
        return {"message": "Cleanup completed", **result}
    except LibraryUnavailable as exc:
        # Library volume not mounted — refuse rather than delete everything.
        db.rollback()
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": exc.code}
        )
    except CleanupRefused as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "code": exc.code,
                "missing": exc.missing,
                "total": exc.total,
            },
        )
    except Exception:
        db.rollback()
        raise
    finally:
        release_job_lock(db, "cleanup")
