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
    raw_title: Optional[str] = None
    raw_artist: Optional[str] = None
    raw_album: Optional[str] = None
    raw_genre: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None
    lastfm_tags_enriched: bool = False

    class Config:
        from_attributes = True