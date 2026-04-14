from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class TrackGenre(Base):
    __tablename__ = "track_genres"

    id = Column(Integer, primary_key=True, index=True)

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    genre = Column(String, nullable=False)

    track = relationship("Track", back_populates="track_genres")

    __table_args__ = (
        UniqueConstraint("track_id", "genre", name="uq_track_genre_pair"),
    )