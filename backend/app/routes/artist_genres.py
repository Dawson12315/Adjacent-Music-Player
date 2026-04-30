from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.user import User

router = APIRouter()


@router.get("/artists/{artist_name:path}/genres", tags=["artists"])
def get_artist_genres(
    artist_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    genres = (
        db.query(Track.genre)
        .filter(Track.artist == artist_name, Track.genre.isnot(None))
        .distinct()
        .order_by(Track.genre.asc())
        .all()
    )

    return [genre for (genre,) in genres if genre]