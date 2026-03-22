from pydantic import BaseModel
from typing import Optional


class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    file_path: str

    class Config:
        from_attributes = True