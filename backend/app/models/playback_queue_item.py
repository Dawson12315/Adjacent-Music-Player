from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.db import Base


class PlaybackQueueItem(Base):
    __tablename__ = "playback_queue_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("playback_sessions.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)

    session = relationship("PlaybackSession", back_populates="queue_items")
    track = relationship("Track")