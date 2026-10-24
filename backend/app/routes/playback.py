from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.track import Track
from app.models.user import User
from app.schemas.playback import PlaybackStateResponse, PlaybackStateUpdate
from app.services.playback import get_or_create_playback_session
from app.services import handoff

router = APIRouter()

# The most queue the server keeps per user: enough for any resume, and
# bounded however large the library is.
MAX_QUEUE_ITEMS = 5000


def _window_queue(track_ids: list[int], queue_index: int) -> tuple[list[int], int]:
    if len(track_ids) <= MAX_QUEUE_ITEMS:
        return list(track_ids), queue_index

    index = queue_index if 0 <= queue_index < len(track_ids) else 0
    start = max(0, min(index - MAX_QUEUE_ITEMS // 2, len(track_ids) - MAX_QUEUE_ITEMS))
    window = track_ids[start : start + MAX_QUEUE_ITEMS]

    return list(window), (queue_index - start if 0 <= queue_index < len(track_ids) else -1)


@router.get("/playback", response_model=PlaybackStateResponse, tags=["playback"])
def get_playback_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_or_create_playback_session(db, current_user.id)
    # The same shape the writes answer with. The read used to leave out the
    # source, so a phone bringing the music here with "Play here" — which
    # reads this — got a bare queue where the other device had a station.
    return _state_response(session)


def _state_response(session) -> dict:
    return {
        "current_track_id": session.current_track_id,
        "queue_index": session.queue_index,
        "current_time_seconds": session.current_time_seconds,
        "is_playing": session.is_playing,
        "is_shuffle": session.is_shuffle,
        "is_loop": session.is_loop,
        "queue_track_ids": [item.track_id for item in session.queue_items],
        "source_type": session.source_type,
        "source_id": session.source_id,
        "version": session.state_version,
        # When the holder last reported, so a device taking the music up can
        # add the time since and land where the holder is now.
        "reported_at": session.reported_at.isoformat() + "Z" if session.reported_at else None,
    }


@router.put("/playback", response_model=PlaybackStateResponse, tags=["playback"])
def update_playback_state(
    payload: PlaybackStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_adjacent_device: str | None = Header(default=None),
):
    session = get_or_create_playback_session(db, current_user.id)

    # This route predates device handoff and still has callers that know
    # nothing of the lease. It must not let a device that is *not* playing
    # overwrite the one that is. The same rule the stream gate uses: the
    # holder writes, a spare or stale lease lets anyone write, and a device
    # that is not the holder while the holder is playing is turned away — a
    # 409 when it named itself, the holder's state unchanged when it did not.
    if not handoff.stream_allowed(db, current_user.id, x_adjacent_device or "legacy-client"):
        if x_adjacent_device:
            raise HTTPException(
                status_code=409,
                detail={"message": "Another device is playing.", "code": "device_not_active"},
            )
        return _state_response(session)

    # "Play all" on a large library sent the whole library: tens of thousands
    # of rows deleted and re-inserted on every debounced save, on the single
    # SQLite writer. Keep a window around the playhead instead.
    queue_ids, queue_index = _window_queue(payload.queue_track_ids, payload.queue_index)

    # Only ids that exist: a track cleanup removed since the client last
    # loaded used to fail the whole save with a foreign-key 500.
    if queue_ids:
        existing = {
            row[0]
            for row in db.query(Track.id).filter(Track.id.in_(queue_ids)).all()
        }
        kept = [track_id for track_id in queue_ids if track_id in existing]
        if len(kept) != len(queue_ids):
            dropped_before = sum(
                1 for track_id in queue_ids[:queue_index] if track_id not in existing
            )
            queue_index = max(-1, queue_index - dropped_before)
            queue_ids = kept

    current_track_id = payload.current_track_id
    if current_track_id is not None and db.get(Track, current_track_id) is None:
        current_track_id = None

    session.current_track_id = current_track_id
    session.queue_index = queue_index
    session.current_time_seconds = payload.current_time_seconds
    session.is_playing = payload.is_playing
    session.is_shuffle = payload.is_shuffle
    session.is_loop = payload.is_loop

    stored_ids = [item.track_id for item in session.queue_items]

    if stored_ids != queue_ids:
        db.query(PlaybackQueueItem).filter(
            PlaybackQueueItem.session_id == session.id
        ).delete(synchronize_session=False)

        for position, track_id in enumerate(queue_ids):
            db.add(
                PlaybackQueueItem(
                    session_id=session.id,
                    track_id=track_id,
                    position=position,
                )
            )

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