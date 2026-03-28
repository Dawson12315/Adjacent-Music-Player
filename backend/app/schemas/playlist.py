from typing import Optional
from pydantic import BaseModel


class PlaylistResponse(BaseModel):
    id: int
    name: str
    is_system: bool
    system_key: Optional[str] = None

    class Config:
        from_attributes = True

class PlaylistCreate(BaseModel):
    name: str

class PlaylistRename(BaseModel):
    name: str

class PlaylistTrackCreate(BaseModel):
    track_id: int