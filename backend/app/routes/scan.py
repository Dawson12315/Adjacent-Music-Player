import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.db import SessionLocal
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.scan import ScanResponse
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.scanner import scan_directory


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scan", response_model=ScanResponse, tags=["scan"])
def run_scan(
    limit: int = Query(20, ge=1),
    current_user: User = Depends(require_admin),
):
    db = SessionLocal()

    if not try_acquire_job_lock(db, "scan"):
        db.close()
        return {"added": 0}

    try:
        logger.info(f"Manual scan requested by {current_user.username} with limit={limit}")
        result = scan_directory(settings.music_library_path, limit=limit)
        logger.info(f"Manual scan finished. Added {result['added']} tracks.")
        return result
    except ValueError as exc:
        # Unmounted or misconfigured library path — a client problem, not a crash.
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        release_job_lock(db, "scan")
        db.close()