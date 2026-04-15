from sqlalchemy import Column, Integer, String
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

    playlist_tracks = relationship("PlaylistTrack", back_populates="track")
    track_artists = relationship("TrackArtist", back_populates="track", cascade="all, delete-orphan")
    track_genres = relationship("TrackGenre", back_populates="track", cascade="all, delete-orphan")