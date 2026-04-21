from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


ListeningEventType = Literal[
    "play_started",
    "play_progress",
    "play_completed",
    "skipped",
    "liked",
    "unliked",
    "queue_added",
    "playlist_added",
    "playlist_removed",
]

SourceType = Literal[
    "playlist",
    "album",
    "artist",
    "library",
    "recommendation",
    "queue",
]


class ListeningEventCreate(BaseModel):
    track_id: int
    event_type: ListeningEventType
    source_type: SourceType | None = None
    source_id: int | None = None
    position_seconds: float | None = None
    duration_seconds: float | None = None
    session_id: str | None = None


class ListeningEventResponse(BaseModel):
    id: int
    track_id: int
    event_type: str
    source_type: str | None
    source_id: int | None
    position_seconds: float | None
    duration_seconds: float | None
    session_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class TrackPlaybackEventBase(BaseModel):
    source_type: SourceType | None = None
    source_id: int | None = None
    position_seconds: float | None = None
    duration_seconds: float | None = None
    session_id: str | None = None


class TrackListeningEventRequest(BaseModel):
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    position_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    session_id: Optional[str] = None