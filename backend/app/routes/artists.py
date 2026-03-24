from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.track import Track

router = APIRouter()

@router.get("/artists", tags=["artists"])
def list_artists(db: Session = Depends(get_db)):
    artists = (
        db.query(Track.artist)
        .filter(Track.artist.isnot(None))
        .group_by(Track.artist)
        .order_by(func.lower(Track.artist))
        .all()
    )
    return [artist[0] for artist in artists if artists[0]]