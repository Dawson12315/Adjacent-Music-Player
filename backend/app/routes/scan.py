from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.db import SessionLocal
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.scan import ScanResponse
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.scanner import scan_directory

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
        print(f"Manual scan requested by {current_user.username} with limit={limit}")
        result = scan_directory(settings.music_library_path, limit=limit)
        print(f"Manual scan finished. Added {result['added']} tracks.")
        return result
    finally:
        release_job_lock(db, "scan")
        db.close()