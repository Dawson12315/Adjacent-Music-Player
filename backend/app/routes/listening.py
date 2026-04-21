from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.listening import (
    ListeningEventCreate,
    ListeningEventResponse,
    TrackPlaybackEventBase,
    TrackListeningEventRequest
)
from app.services.listening_service import record_listening_event

router = APIRouter()


@router.post(
    "/listening-events",
    response_model=ListeningEventResponse,
    tags=["listening"],
)
def create_listening_event(
    payload: ListeningEventCreate,
    db: Session = Depends(get_db),
):
    try:
        event = record_listening_event(db, payload)
        return event
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/tracks/{track_id}/play-start",
    response_model=ListeningEventResponse,
    tags=["listening"],
)
def track_play_start(
    track_id: int,
    payload: TrackPlaybackEventBase,
    db: Session = Depends(get_db),
):
    try:
        event = record_listening_event(
            db,
            ListeningEventCreate(
                track_id=track_id,
                event_type="play_started",
                source_type=payload.source_type,
                source_id=payload.source_id,
                position_seconds=payload.position_seconds,
                duration_seconds=payload.duration_seconds,
                session_id=payload.session_id,
            ),
        )
        return event
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/tracks/{track_id}/play-complete",
    response_model=ListeningEventResponse,
    tags=["listening"],
)
def track_play_complete(
    track_id: int,
    payload: TrackPlaybackEventBase,
    db: Session = Depends(get_db),
):
    try:
        event = record_listening_event(
            db,
            ListeningEventCreate(
                track_id=track_id,
                event_type="play_completed",
                source_type=payload.source_type,
                source_id=payload.source_id,
                position_seconds=payload.position_seconds,
                duration_seconds=payload.duration_seconds,
                session_id=payload.session_id,
            ),
        )
        return event
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/tracks/{track_id}/skip",
    response_model=ListeningEventResponse,
    tags=["listening"],
)
def track_skip(
    track_id: int,
    payload: TrackPlaybackEventBase,
    db: Session = Depends(get_db),
):
    try:
        event = record_listening_event(
            db,
            ListeningEventCreate(
                track_id=track_id,
                event_type="skipped",
                source_type=payload.source_type,
                source_id=payload.source_id,
                position_seconds=payload.position_seconds,
                duration_seconds=payload.duration_seconds,
                session_id=payload.session_id,
            ),
        )
        return event
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    

@router.post("/tracks/{track_id}/like", response_model=ListeningEventResponse, tags=["listening"])
def like_track(
    track_id: int,
    payload: TrackListeningEventRequest,
    db: Session = Depends(get_db),
):
    event = record_listening_event(
        db,
        ListeningEventCreate(
            track_id=track_id,
            event_type="liked",
            source_type=payload.source_type,
            source_id=payload.source_id,
            position_seconds=payload.position_seconds,
            duration_seconds=payload.duration_seconds,
            session_id=payload.session_id,
        ),
    )
    return event


@router.post("/tracks/{track_id}/unlike", response_model=ListeningEventResponse, tags=["listening"])
def unlike_track(
    track_id: int,
    payload: TrackListeningEventRequest,
    db: Session = Depends(get_db),
):
    event = record_listening_event(
        db,
        ListeningEventCreate(
            track_id=track_id,
            event_type="unliked",
            source_type=payload.source_type,
            source_id=payload.source_id,
            position_seconds=payload.position_seconds,
            duration_seconds=payload.duration_seconds,
            session_id=payload.session_id,
        ),
    )
    return event