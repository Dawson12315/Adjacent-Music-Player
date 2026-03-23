from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

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

@router.get("/tracks/{track_id}/stream", tags=["tracks"])
def stream_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=file_path.name,
    )