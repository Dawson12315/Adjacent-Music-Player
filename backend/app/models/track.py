from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.db import Base


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=True)
    album = Column(String, nullable=True)
    genre = Column(String, nullable=True)
    file_path = Column(String, nullable=False, unique=True)
    raw_title = Column(String, nullable=True)
    raw_artist = Column(String, nullable=True)
    raw_album = Column(String, nullable=True)
    raw_genre = Column(String, nullable=True)
    musicbrainz_recording_id = Column(String, nullable=True, index=True)
    lastfm_tags_enriched = Column(Boolean, nullable=False, default=False)
    duration_seconds = Column(Float, nullable=True)

    # Set by cleanup the first time the file cannot be found, cleared the
    # moment it is found again. A track is only deleted once it has stayed
    # missing for the whole grace period, so a NAS that drops for a night
    # costs nothing.
    missing_since = Column(DateTime, nullable=True)

    # When the MusicBrainz and Last.fm lookups last ran for this track, matched
    # or not. Without these an unmatchable track was retried on every pass —
    # the backfill hammered the same fifty tracks for the life of the process.
    musicbrainz_checked_at = Column(DateTime, nullable=True)
    lastfm_checked_at = Column(DateTime, nullable=True)

    # The file's identity beyond its path: a moved file keeps its size and
    # modification time, which is how the scanner recognises it instead of
    # importing it again and losing its history to cleanup.
    # Big integers: a nanosecond timestamp is 1.7e18 and a lossless album
    # side can pass two gigabytes; Postgres's plain integer is 32-bit.
    file_size = Column(BigInteger, nullable=True)
    file_mtime_ns = Column(BigInteger, nullable=True)

    # The track list sorts on lower(column) and the section jump counts on
    # it; declared here, not only in the SQLite migration runner, so Postgres
    # gets them too and the two schemas stop drifting.
    __table_args__ = (
        Index("ix_tracks_genre", "genre"),
        Index("ix_tracks_lower_artist", func.lower(artist)),
        Index("ix_tracks_lower_album", func.lower(album)),
        Index("ix_tracks_lower_title", func.lower(title)),
    )

    playlist_tracks = relationship("PlaylistTrack", back_populates="track")
    track_artists = relationship("TrackArtist", back_populates="track", cascade="all, delete-orphan")
    track_genres = relationship("TrackGenre", back_populates="track", cascade="all, delete-orphan")