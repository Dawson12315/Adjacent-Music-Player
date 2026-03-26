from pydantic import BaseModel


class PlaylistResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class PlaylistCreate(BaseModel):
    name: str