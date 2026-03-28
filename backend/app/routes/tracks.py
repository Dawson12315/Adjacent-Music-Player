from pathlib import Path
import mimetypes
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.track import Track
from app.schemas.track import TrackResponse

from app.models.playlist_track import PlaylistTrack
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
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
    
    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
    )

@router.delete("/tracks/purge", tags=["tracks"])
def purge_tracks(db: Session = Depends(get_db)):
    deleted_tracks = db.query(Track).count()

    # Clears playlist-track relationships
    db.query(PlaylistTrack).delete()

    # Clears playback queue
    db.query(PlaybackQueueItem).delete()

    # Reset playback session to a default
    session = db.query(PlaybackSession).first()
    if session:
        session.current_track_id = None
        session.queue_index = -1
        session.current_time_seconds = 0
        session.is_playing = False

    # Delete Tracks
    db.query(Track).delete()

    db.commit()

    return {
        "message": "All stored tracks purged",
        "deleted_count": deleted_tracks,
    }