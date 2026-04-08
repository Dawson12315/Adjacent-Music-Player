from pydantic import BaseModel


class ArtistRenameRequest(BaseModel):
    current_artist: str
    new_artist: str


class ArtistTransferRequest(BaseModel):
    source_artist: str
    target_artist: str