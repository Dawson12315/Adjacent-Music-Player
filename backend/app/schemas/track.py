from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    artists: List[str] = Field(default_factory=list)
    file_path: str
    artwork_path: Optional[str] = None
    album_artwork_path: Optional[str] = None
    artist_artwork_path: Optional[str] = None
    raw_title: Optional[str] = None
    raw_artist: Optional[str] = None
    raw_album: Optional[str] = None
    raw_genre: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None
    lastfm_tags_enriched: bool = False
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class TrackWithStatsResponse(TrackResponse):
    play_count: int = 0
    skip_count: int = 0
    completion_count: int = 0
    like_count: int = 0
    last_played_at: Optional[datetime] = None
