from fastapi import APIRouter

from app.config import settings
from app.schemas.scan import ScanResponse
from app.services.scanner import scan_directory

router = APIRouter()


@router.post("/scan", response_model=ScanResponse, tags=["scan"])
def run_scan():
    result = scan_directory(settings.music_library_path, limit=20)
    return result