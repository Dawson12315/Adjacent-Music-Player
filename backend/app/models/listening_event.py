from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class ListeningEvent(Base):
    __tablename__ = "listening_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=True)
    source_id = Column(Integer, nullable=True)
    position_seconds = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    session_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    track = relationship("Track")