from fastapi import APIRouter

from app.config import settings
from app.services.scanner import scan_directory

router = APIRouter()


@router.post("/scan", tags=["scan"])
def run_scan():
    result = scan_directory(settings.music_library_path, limit=20)
    return result