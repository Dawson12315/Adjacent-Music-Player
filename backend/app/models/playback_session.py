from sqlalchemy import Boolean, Column, ForeignKey, Integer
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

    current_track = relationship("Track")
    queue_items = relationship(
        "PlaybackQueueItem",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PlaybackQueueItem.position",
    )