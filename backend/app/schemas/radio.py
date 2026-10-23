from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.track import TrackResponse

SeedType = Literal["track", "album", "artist"]


class RadioStationCreate(BaseModel):
    """What a station is made from. One of the seed fields, matching
    `seed_type`: a track id, an album name (with the artist it is filed
    under, when known), or an artist name."""

    seed_type: SeedType
    seed_track_id: Optional[int] = None
    seed_album: Optional[str] = Field(default=None, max_length=600)
    seed_album_artist: Optional[str] = Field(default=None, max_length=300)
    seed_artist: Optional[str] = Field(default=None, max_length=300)

    @field_validator("seed_album", "seed_album_artist", "seed_artist", mode="before")
    @classmethod
    def _clean(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RadioStationResponse(BaseModel):
    id: int
    seed_type: str
    seed_track_id: Optional[int] = None
    seed_album: Optional[str] = None
    seed_album_artist: Optional[str] = None
    seed_artist: Optional[str] = None
    name: str
    artwork_path: Optional[str] = None
    created_at: datetime
    last_played_at: datetime


class RadioTrackResponse(TrackResponse):
    # One line on why the station chose this track, for the player.
    reason: Optional[str] = None


class RadioNextResponse(BaseModel):
    station: RadioStationResponse
    tracks: list[RadioTrackResponse]
    # The library could not fill the batch even after relaxing the station's
    # memory: the client may say so, and should expect repeats soon.
    thin: bool = False


class RadioPlayedRequest(BaseModel):
    track_ids: list[int] = Field(default_factory=list, max_length=200)
