from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint

from app.db import Base


class RadioStation(Base):
    """A radio station: one listener's seed, plus a name to list it under.

    A station is made from one track, one album or one artist. Albums and
    artists are names in this schema rather than rows, so the seed is kept
    as the names themselves, and `seed_key` folds whichever seed it is into
    one comparable string so the same seed always comes back as the same
    station ("Fen radio" exists once per listener).
    """

    __tablename__ = "radio_stations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    seed_type = Column(String(16), nullable=False)
    seed_track_id = Column(Integer, nullable=True)
    seed_album = Column(String, nullable=True)
    seed_album_artist = Column(String, nullable=True)
    seed_artist = Column(String, nullable=True)
    seed_key = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_played_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "seed_key", name="uq_radio_station_seed"),
        Index("ix_radio_stations_recent", "user_id", "last_played_at"),
    )


class RadioStationPlay(Base):
    """What a station has played, so it does not come back round too soon.

    Pruned to the last `MEMORY` rows per station on every write.
    """

    __tablename__ = "radio_station_plays"

    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, nullable=False)
    track_id = Column(Integer, nullable=False)
    played_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_radio_station_plays_station", "station_id", "played_at"),
    )
