from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, UniqueConstraint

from app.db import Base


class RecommendationDismissal(Base):
    """A track a listener recycled out of one playlist's suggestions.

    Kept for a few days and scoped to that playlist: the same track can
    still be suggested for another playlist, and comes back here once the
    hold expires. Pruned by the nightly cleanup.
    """

    __tablename__ = "recommendation_dismissals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    playlist_id = Column(Integer, nullable=False)
    track_id = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "playlist_id", "track_id", name="uq_recommendation_dismissal"),
        Index("ix_recommendation_dismissals_scope", "user_id", "playlist_id", "expires_at"),
    )
