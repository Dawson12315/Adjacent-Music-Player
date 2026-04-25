from sqlalchemy import Column, DateTime, Integer, String, Float, UniqueConstraint, func
from app.db import Base


class ArtistLastfmSimilarity(Base):
    __tablename__ = "artist_lastfm_similarity"

    id = Column(Integer, primary_key=True, index=True)

    source_artist_name = Column(String, nullable=False)
    source_artist_key = Column(String, nullable=False, index=True)

    similar_artist_name = Column(String, nullable=False)
    similar_artist_key = Column(String, nullable=False, index=True)

    match_score = Column(Float, nullable=True)

    source_mbid = Column(String, nullable=True)
    similar_mbid = Column(String, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "source_artist_key",
            "similar_artist_key",
            name="uq_artist_similarity_pair"
        ),
    )