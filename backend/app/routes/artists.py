from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.track_artist import TrackArtist

router = APIRouter()


@router.get("/artists", tags=["artists"])
def list_artists(db: Session = Depends(get_db)):
    artists = (
        db.query(TrackArtist.artist_name)
        .filter(TrackArtist.artist_name.isnot(None))
        .group_by(TrackArtist.artist_name)
        .order_by(func.lower(TrackArtist.artist_name))
        .all()
    )

    return [artist[0] for artist in artists if artist[0]]