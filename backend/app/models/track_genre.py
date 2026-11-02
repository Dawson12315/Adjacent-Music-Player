from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class TrackGenre(Base):
    __tablename__ = "track_genres"

    id = Column(Integer, primary_key=True, index=True)

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    genre = Column(String, nullable=False)
    # How strongly the tag applies (Last.fm's 0–100 count), and where the row
    # came from: "file" for the scanner, "lastfm" for enrichment, "legacy"
    # for rows written before either was recorded. Both nullable so older
    # installs gain the columns at boot; a missing weight reads as "full".
    weight = Column(Integer, nullable=True)
    source = Column(String(16), nullable=True)

    track = relationship("Track", back_populates="track_genres")

    __table_args__ = (
        UniqueConstraint("track_id", "genre", name="uq_track_genre_pair"),
        Index("ix_track_genres_genre", "genre"),
    )