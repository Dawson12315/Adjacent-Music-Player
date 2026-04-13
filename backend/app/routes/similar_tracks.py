from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from app.db import get_db
from app.models.track import Track

router = APIRouter()


@router.get("/tracks/{track_id}/similar", tags=["tracks"])
def get_similar_tracks(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track or not track.genre:
        return []

    similar_tracks = (
        db.query(Track)
        .filter(
            Track.genre == track.genre,
            Track.id != track.id
        )
        .order_by(func.random())
        .limit(10)
        .all()
    )

    return similar_tracks