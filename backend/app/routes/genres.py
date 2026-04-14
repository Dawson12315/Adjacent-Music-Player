from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.track_genre import TrackGenre

router = APIRouter()


@router.get("/genres", tags=["genres"])
def list_genres(db: Session = Depends(get_db)):
    genres = (
        db.query(TrackGenre.genre)
        .distinct()
        .order_by(func.lower(TrackGenre.genre))
        .all()
    )

    return [g[0] for g in genres if g[0]]