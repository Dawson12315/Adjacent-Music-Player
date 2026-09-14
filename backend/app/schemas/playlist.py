from typing import List, Optional
from pydantic import BaseModel, Field


class PlaylistPreviewItem(BaseModel):
    """One of the first few distinct albums in a playlist, for a cover mosaic.

    `artwork_path` is the album's cover when the server has one; clients draw
    their generated tile from `album` (or `title` when the track has no album)
    when it is null, the same way they do for a track row.
    """

    title: str
    album: Optional[str] = None
    artwork_path: Optional[str] = None


class PlaylistResponse(BaseModel):
    id: int
    name: str
    is_system: bool
    system_key: Optional[str] = None
    artwork_path: Optional[str] = None
    track_count: int = 0
    preview: List[PlaylistPreviewItem] = Field(default_factory=list)

    class Config:
        from_attributes = True

class PlaylistCreate(BaseModel):
    name: str

class PlaylistRename(BaseModel):
    name: str

class PlaylistTrackCreate(BaseModel):
    track_id: int
