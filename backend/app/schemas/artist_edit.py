from pydantic import BaseModel, Field, field_validator

from app.schemas.track_edit import MAX_TEXT_FIELD, _clean_text


def _required_name(value):
    cleaned = _clean_text(value)
    if not cleaned:
        raise ValueError("Artist names cannot be empty")
    return cleaned


class ArtistRenameRequest(BaseModel):
    current_artist: str = Field(min_length=1, max_length=MAX_TEXT_FIELD)
    new_artist: str = Field(min_length=1, max_length=MAX_TEXT_FIELD)

    @field_validator("current_artist", "new_artist", mode="before")
    @classmethod
    def _names(cls, value):
        return _required_name(value)


class ArtistTransferRequest(BaseModel):
    source_artist: str = Field(min_length=1, max_length=MAX_TEXT_FIELD)
    target_artist: str = Field(min_length=1, max_length=MAX_TEXT_FIELD)

    @field_validator("source_artist", "target_artist", mode="before")
    @classmethod
    def _names(cls, value):
        return _required_name(value)
