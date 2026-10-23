from sqlalchemy import Column, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.db import Base


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)

    playlist = relationship("Playlist", back_populates="playlist_tracks")
    track = relationship("Track", back_populates="playlist_tracks")

    # Every heart check, liked-ids read and playlist page filters on one of
    # these; without them each was a scan of every playlist row in the
    # library. The pair is unique: a double tap on "add" used to insert the
    # track twice, since the existence check and the insert were two steps.
    # Created on both engines by sync_model_indexes, after the one-time
    # dedupe in db_migrations clears any pairs an older install let in.
    __table_args__ = (
        Index("ix_playlist_tracks_pair", "playlist_id", "track_id", unique=True),
        Index("ix_playlist_tracks_track_id", "track_id"),
    )