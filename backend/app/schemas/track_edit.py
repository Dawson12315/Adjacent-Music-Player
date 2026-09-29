from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# Long enough for any real title, short enough that a pasted document is
# refused rather than stored.
MAX_TEXT_FIELD = 300


def _clean_text(value):
    """Strip control characters and surrounding whitespace; None for empty."""
    if value is None:
        return None
    text = "".join(ch if ch.isprintable() or ch == " " else " " for ch in str(value))
    text = " ".join(text.split())
    return text or None


class TrackUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TEXT_FIELD)
    artist: Optional[str] = Field(default=None, max_length=MAX_TEXT_FIELD)
    album: Optional[str] = Field(default=None, max_length=MAX_TEXT_FIELD)
    genres: Optional[List[str]] = None

    @field_validator("title", mode="before")
    @classmethod
    def _title_present(cls, value):
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("A track needs a title")
        return cleaned

    @field_validator("artist", "album", mode="before")
    @classmethod
    def _optional_text(cls, value):
        return _clean_text(value)

    @field_validator("genres", mode="before")
    @classmethod
    def _genre_names(cls, value):
        if value is None:
            return None
        cleaned = [_clean_text(item) for item in value]
        return [item[:MAX_TEXT_FIELD] for item in cleaned if item]
