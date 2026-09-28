from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


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

SOURCE_TYPES = set(SourceType.__args__)


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
    # Coerced rather than rejected: a client naming a source this server does
    # not know (a newer app, a typo) still records the event, without it.
    # Leaving this a bare string let the value reach the Literal below and
    # turn every such like into a 500.
    source_type: Optional[str] = None

    @field_validator("source_type", mode="before")
    @classmethod
    def _known_source_or_none(cls, value):
        if value is None:
            return None
        text = str(value).strip().lower()
        return text if text in SOURCE_TYPES else None
    source_id: Optional[int] = None
    position_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    session_id: Optional[str] = None