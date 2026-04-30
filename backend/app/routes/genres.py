from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track_genre import TrackGenre
from app.models.user import User

router = APIRouter()


@router.get("/genres", tags=["genres"])
def list_genres(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    genres = (
        db.query(TrackGenre.genre)
        .distinct()
        .order_by(func.lower(TrackGenre.genre))
        .all()
    )

    return [g[0] for g in genres if g[0]]