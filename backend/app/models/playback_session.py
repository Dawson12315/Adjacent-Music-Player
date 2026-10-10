from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class PlaybackSession(Base):
    __tablename__ = "playback_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True, index=True)

    current_track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    queue_index = Column(Integer, nullable=False, default=-1)
    current_time_seconds = Column(Integer, nullable=False, default=0)
    is_playing = Column(Boolean, nullable=False, default=False)
    is_shuffle = Column(Boolean, nullable=False, default=False)
    is_loop = Column(Boolean, nullable=False, default=False)

    # The lease: which of the user's devices is playing. A plain integer
    # rather than a foreign key so the column can be added to a live
    # install by the start-up schema sync on both engines; the handoff
    # service keeps it pointing at a real row.
    active_device_id = Column(Integer, nullable=True)
    active_since = Column(DateTime, nullable=True)
    # Where the queue came from, so the device that takes it over can carry
    # on from the same list; the listening events use the same pair.
    source_type = Column(String(32), nullable=True)
    source_id = Column(Integer, nullable=True)
    # Counts up with every accepted state; a late report with an older
    # version is ignored rather than winding the position back.
    state_version = Column(Integer, nullable=True)
    # When the holder last reported; what a remote's clock runs from.
    reported_at = Column(DateTime, nullable=True)

    current_track = relationship("Track")
    queue_items = relationship(
        "PlaybackQueueItem",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PlaybackQueueItem.position",
    )
