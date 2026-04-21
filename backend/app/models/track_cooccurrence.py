from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base


class TrackCooccurrence(Base):
    __tablename__ = "track_cooccurrence"

    id = Column(Integer, primary_key=True, index=True)
    track_a_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    track_b_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    cooccurrence_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", name="uq_track_cooccurrence_pair"),
    )

    track_a = relationship("Track", foreign_keys=[track_a_id])
    track_b = relationship("Track", foreign_keys=[track_b_id])