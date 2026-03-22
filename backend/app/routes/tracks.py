from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.track import Track
from app.schemas.track import TrackResponse

router = APIRouter()


@router.get("/tracks", tags=["tracks"])
def list_tracks(db: Session = Depends(get_db)):
    tracks = db.query(Track).all()
    return tracks