from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db import Base


class ArtistLastfmCheck(Base):
    """When an artist in the library was last asked for on Last.fm.

    Similar-artist rows only exist for artists Last.fm had neighbours for, so
    without this an artist it knew nothing about would be asked again every
    night. One row per normalised artist name; `similar_count` is what the
    last answer held.
    """

    __tablename__ = "artist_lastfm_checks"

    artist_key = Column(String, primary_key=True)
    artist_name = Column(String, nullable=False)
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    similar_count = Column(Integer, nullable=False, default=0)
