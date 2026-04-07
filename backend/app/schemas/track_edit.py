from typing import Optional

from pydantic import BaseModel


class TrackUpdate(BaseModel):
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None