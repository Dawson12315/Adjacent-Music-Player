from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.track import Track

router = APIRouter()


@router.get("/genres", tags=["genres"])
def list_genres(db: Session = Depends(get_db)):
    genres = (
        db.query(Track.genre)
        .filter(Track.genre.isnot(None))
        .distinct()
        .order_by(Track.genre.asc())
        .all()
    )

    return [genre for (genre,) in genres if genre]