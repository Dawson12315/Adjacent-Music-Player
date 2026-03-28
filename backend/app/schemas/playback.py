from typing import List, Optional

from pydantic import BaseModel


class PlaybackStateResponse(BaseModel):
    current_track_id: Optional[int] = None
    queue_index: int
    current_time_seconds: int
    is_playing: bool
    is_shuffle: bool
    is_loop: bool
    queue_track_ids: List[int]

class PlaybackStateUpdate(BaseModel):
    current_track_id: Optional[int] = None
    queue_index: int
    current_time_seconds: int
    is_playing: bool
    is_shuffle: bool
    is_loop: bool
    queue_track_ids: List[int]