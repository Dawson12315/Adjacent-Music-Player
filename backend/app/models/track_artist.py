from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class TrackArtist(Base):
    __tablename__ = "track_artists"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    artist_name = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)

    track = relationship("Track", back_populates="track_artists")

    __table_args__ = (
        UniqueConstraint("track_id", "artist_name", name="uq_track_artist_pair"),
    )