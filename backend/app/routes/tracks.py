from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.track import Track
from app.schemas.track import TrackResponse

router = APIRouter()


@router.get("/tracks/count", tags=["tracks"])
def get_track_count(db: Session = Depends(get_db)):
    count = db.query(func.count(Track.id)).scalar()
    return {"count": count}

@router.get("/tracks", response_model=list[TrackResponse], tags=["tracks"])
def list_tracks(db: Session = Depends(get_db)):
    tracks = (
        db.query(Track)
        .order_by(Track.artist.asc(), Track.album.asc(), Track.title.asc())
        .all()
    )
    return tracks