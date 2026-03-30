from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.maintenance import cleanup_missing_tracks

router = APIRouter()


@router.post("/maintenance/cleanup", tags=["maintenance"])
def run_cleanup(db: Session = Depends(get_db)):
    result = cleanup_missing_tracks(db)
    return result