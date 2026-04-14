from typing import List, Optional

from pydantic import BaseModel


class TrackUpdate(BaseModel):
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    genres: Optional[List[str]] = None