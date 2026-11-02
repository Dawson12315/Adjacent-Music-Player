from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String

from app.db import Base


class TrackVector(Base):
    """Where a track sits in the map: `dim` little-endian float32 values.

    Derived data, rebuilt nightly and after a scan by
    `recommendations.vector_map`; never edited by hand, never migrated.
    """

    __tablename__ = "track_vectors"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    vector = Column(LargeBinary, nullable=False)
    dim = Column(Integer, nullable=False)
    built_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ArtistVector(Base):
    """Where an artist sits in the map, keyed by the normalised name."""

    __tablename__ = "artist_vectors"

    artist_key = Column(String, primary_key=True)
    artist_name = Column(String, nullable=False)
    vector = Column(LargeBinary, nullable=False)
    dim = Column(Integer, nullable=False)
    built_at = Column(DateTime, nullable=False, default=datetime.utcnow)
