from fastapi import APIRouter, Query

from app.config import settings
from app.schemas.scan import ScanResponse
from app.services.scanner import scan_directory

router = APIRouter()


@router.post("/scan", response_model=ScanResponse, tags=["scan"])
def run_scan(limit: int = Query(20, ge=1, le=1000)):
    result = scan_directory(settings.music_library_path, limit=limit)
    return result