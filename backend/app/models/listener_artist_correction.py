from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, UniqueConstraint

from app.db import Base


class ListenerArtistCorrection(Base):
    """One listener's standing correction to where an artist sits on the map.

    Thumbs on a station nudge this: toward the station's seeds for "more",
    away for "less" and "less of this artist". It is a small bounded vector
    added to the artist's position for this listener only, and it outlives
    the station. One row per (listener, artist); fifteen listeners who each
    vote on three hundred artists is under a megabyte.
    """

    __tablename__ = "listener_artist_corrections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    artist_key = Column(String, nullable=False)
    artist_name = Column(String, nullable=True)
    delta = Column(LargeBinary, nullable=False)
    dim = Column(Integer, nullable=False)
    votes_up = Column(Integer, nullable=False, default=0)
    votes_down = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "artist_key", name="uq_listener_artist_correction"),)
