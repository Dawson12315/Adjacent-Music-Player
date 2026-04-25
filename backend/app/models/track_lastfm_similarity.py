from sqlalchemy import Column, DateTime, Integer, String, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base


class TrackLastfmSimilarity(Base):
    __tablename__ = "track_lastfm_similarity"

    id = Column(Integer, primary_key=True, index=True)

    # Local track references (preferred for fast joins later)
    source_track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)
    similar_track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True, index=True)

    # Raw Last.fm identity (used before resolution OR as fallback)
    source_track_name = Column(String, nullable=False)
    source_artist_name = Column(String, nullable=False)

    similar_track_name = Column(String, nullable=False)
    similar_artist_name = Column(String, nullable=False)

    source_track_key = Column(String, nullable=False, index=True)
    similar_track_key = Column(String, nullable=False, index=True)

    match_score = Column(Float, nullable=True)

    source_mbid = Column(String, nullable=True)
    similar_mbid = Column(String, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships (optional but useful later)
    source_track = relationship(
        "Track",
        foreign_keys=[source_track_id],
        lazy="joined"
    )

    similar_track = relationship(
        "Track",
        foreign_keys=[similar_track_id],
        lazy="joined"
    )

    __table_args__ = (
        UniqueConstraint(
            "source_track_id",
            "similar_track_key",
            name="uq_track_similarity_pair"
        ),
    )