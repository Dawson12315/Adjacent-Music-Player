from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class TrackUserStats(Base):
    __tablename__ = "track_user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)

    play_count = Column(Integer, nullable=False, default=0)
    skip_count = Column(Integer, nullable=False, default=0)
    completion_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)

    avg_completion_ratio = Column(Float, nullable=False, default=0.0)
    replay_score = Column(Float, nullable=False, default=0.0)

    playlist_add_count = Column(Integer, nullable=False, default=0)

    last_played_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    track = relationship("Track")

    __table_args__ = (
        UniqueConstraint("user_id", "track_id", name="uq_track_user_stats_user_track"),
    )