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


FeedbackKind = Literal["more", "less", "less_artist"]


class RadioFeedbackResponse(BaseModel):
    """What the listener has said about a station: tracks that joined the
    seeds, tracks kept off it, artists kept out of its neighbours."""

    more_track_ids: list[int] = Field(default_factory=list)
    less_track_ids: list[int] = Field(default_factory=list)
    less_artists: list[str] = Field(default_factory=list)


class RadioTasteResponse(BaseModel):
    """The listener's standing corrections to the map, in counts."""

    artists: int = 0
    votes_up: int = 0
    votes_down: int = 0
    cleared: Optional[int] = None


class RadioFeedbackRequest(BaseModel):
    track_id: int
    kind: FeedbackKind


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
    # Present on the single-station routes; the recent list leaves it out.
    feedback: Optional[RadioFeedbackResponse] = None


class RadioTrackResponse(TrackResponse):
    # One line on why the station chose this track, for the player.
    reason: Optional[str] = None


class RadioNextResponse(BaseModel):
    station: RadioStationResponse
    tracks: list[RadioTrackResponse]
    # The seeds' corner of the library could not fill the batch: the station
    # reached wider for the rest. The client may say so, once.
    thin: bool = False
    # How far it reached, widest step: "genre" (the seeds' genres), "artist"
    # (the seed artist's other genres), "listener" (what you play most),
    # "library" (anywhere), "again" (round again, memory set aside). None
    # when the batch came from the recommender and the seed's own material.
    reach: Optional[str] = None


class RadioLineupResponse(BaseModel):
    station: RadioStationResponse
    # The lineup from the track the listener got to, onward. Empty when the
    # station has never played, or its lineup is older than ten days.
    tracks: list[RadioTrackResponse]
    resumable: bool = False
    saved_at: Optional[datetime] = None


class RadioPlayedRequest(BaseModel):
    track_ids: list[int] = Field(default_factory=list, max_length=200)
