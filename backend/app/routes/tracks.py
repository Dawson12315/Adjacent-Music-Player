from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.track import Track

router = APIRouter()


@router.get("/tracks", tags=["tracks"])
def list_tracks(db: Session = Depends(get_db)):
    tracks = db.query(Track).all()

    return [
        {
            "id": track.id,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "file_path": track.file_path
        }
        for track in tracks
    ]