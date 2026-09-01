import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.scan import ScanStartResponse
from app.services.scan_runner import get_scan_progress, start_scan_background

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scan", response_model=ScanStartResponse, tags=["scan"])
def run_scan(
    limit: int = 100000,
    current_user: User = Depends(require_admin),
):
    """Kick off a background library scan.

    The scan used to run inside this request; on a large library over a
    network mount that blocked for up to an hour, died with the connection,
    and orphaned the job lock. Poll /scan/progress for status.
    """
    result = start_scan_background(limit)

    logger.info(
        "Scan requested by %s: %s", current_user.username, result["reason"]
    )

    return result


@router.get("/scan/progress", tags=["scan"])
def scan_progress(
    current_user: User = Depends(get_current_user),
):
    response = JSONResponse(content=get_scan_progress())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response
