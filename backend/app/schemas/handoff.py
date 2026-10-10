"""What a device says about itself, and what it asks for."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.playback import PlaybackStateUpdate

DeviceKind = Literal["phone", "tablet", "web", "other"]

COMMANDS = ("play", "pause", "next", "previous", "seek", "shuffle", "repeat", "volume")


class DeviceInfo(BaseModel):
    """The `hello`: who this device is. Sent on connect and when the name changes."""

    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    kind: DeviceKind = "other"
    platform: Optional[str] = Field(default=None, max_length=32)
    app_version: Optional[str] = Field(default=None, max_length=24)
    # "carplay" while the phone is in a car; the pickers say so.
    context: Optional[str] = Field(default=None, max_length=16)


class ClaimBody(BaseModel):
    state: PlaybackStateUpdate


class PositionReport(BaseModel):
    """The cheap, frequent write: where the holder is, nothing about the queue."""

    current_track_id: Optional[int] = None
    queue_index: Optional[int] = None
    current_time_seconds: int = 0
    is_playing: bool = False
    is_shuffle: Optional[bool] = None
    is_loop: Optional[bool] = None
    version: Optional[int] = None


class TransferBody(BaseModel):
    to: str = Field(min_length=1, max_length=64)
    state: Optional[PlaybackStateUpdate] = None


class CommandBody(BaseModel):
    action: Literal["play", "pause", "next", "previous", "seek", "shuffle", "repeat", "volume"]
    args: dict[str, Any] = Field(default_factory=dict)
