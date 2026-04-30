from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.user import User
from app.schemas.playback import PlaybackStateResponse, PlaybackStateUpdate
from app.services.playback import get_or_create_playback_session

router = APIRouter()


@router.get("/playback", response_model=PlaybackStateResponse, tags=["playback"])
def get_playback_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.put("/playback", response_model=PlaybackStateResponse, tags=["playback"])
def update_playback_state(
    payload: PlaybackStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_or_create_playback_session(db)

    session.current_track_id = payload.current_track_id
    session.queue_index = payload.queue_index
    session.current_time_seconds = payload.current_time_seconds
    session.is_playing = payload.is_playing
    session.is_shuffle = payload.is_shuffle
    session.is_loop = payload.is_loop

    db.query(PlaybackQueueItem).filter(
        PlaybackQueueItem.session_id == session.id
    ).delete(synchronize_session=False)

    for position, track_id in enumerate(payload.queue_track_ids):
        queue_item = PlaybackQueueItem(
            session_id=session.id,
            track_id=track_id,
            position=position,
        )
        db.add(queue_item)

    db.commit()
    db.refresh(session)

    return {
        "current_track_id": session.current_track_id,
        "queue_index": session.queue_index,
        "current_time_seconds": session.current_time_seconds,
        "is_playing": session.is_playing,
        "is_shuffle": session.is_shuffle,
        "is_loop": session.is_loop,
        "queue_track_ids": [item.track_id for item in session.queue_items],
    }