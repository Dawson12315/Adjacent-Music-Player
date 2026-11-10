from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LyricLine(BaseModel):
    t: float = Field(ge=0)
    line: str = Field(max_length=2000)


class LyricsResponse(BaseModel):
    track_id: int
    # Where the words came from: embedded, sidecar, user, transcribed.
    source: str
    # Where the timing came from, when there is timing: embedded, sidecar,
    # user, aligned, transcribed.
    synced_source: Optional[str] = None
    plain: str
    synced: Optional[list[LyricLine]] = None
    language: Optional[str] = None
    # True when any part of this was produced by the server's model, so the
    # clients can say so.
    generated: bool = False
    model: Optional[str] = None
    confidence: Optional[float] = None
    updated_at: Optional[str] = None


class LyricsUpdate(BaseModel):
    """Typed, pasted or corrected lyrics. Plain text, timed lines, or both;
    LRC pasted into `plain` is understood."""

    plain: Optional[str] = Field(default=None, max_length=64_000)
    synced: Optional[list[LyricLine]] = Field(default=None, max_length=3000)

    @field_validator("synced")
    @classmethod
    def _ordered(cls, value):
        if value is None:
            return value
        return sorted(value, key=lambda line: line.t)


class LyricsGenerationStatus(BaseModel):
    state: str
    reason: Optional[str] = None
