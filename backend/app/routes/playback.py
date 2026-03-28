from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.playback import PlaybackStateResponse
from app.services.playback import get_or_create_playback_session

router = APIRouter()


@router.get("/playback", response_model=PlaybackStateResponse, tags=["playback"])
def get_playback_state(db: Session = Depends(get_db)):
    session = get_or_create_playback_session(db)

    return {
        "current_track_id": session.current_track_id,
        "queue_index": session.queue_index,
        "current_time_seconds": session.current_time_seconds,
        "is_playing": session.is_playing,
        "is_shuffle": session.is_shuffle,
        "is_loop": session.is_loop,
        "queue_track_ids": [item.track_id for item in session.queue_items],
    }