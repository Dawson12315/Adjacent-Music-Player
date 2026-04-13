from pydantic import BaseModel
from typing import Optional


class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    file_path: str
    raw_title: Optional[str] = None
    raw_artist: Optional[str] = None
    raw_album: Optional[str] = None
    raw_genre: Optional[str] = None

    class Config:
        from_attributes = True