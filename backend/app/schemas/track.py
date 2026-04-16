from pydantic import BaseModel
from typing import List, Optional


class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    genres: List[str] = []
    file_path: str
    raw_title: Optional[str] = None
    raw_artist: Optional[str] = None
    raw_album: Optional[str] = None
    raw_genre: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None
    lastfm_tags_enriched: bool = False

    class Config:
        from_attributes = True