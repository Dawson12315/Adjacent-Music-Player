from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    is_system = Column(Boolean, nullable=False, default=False)
    system_key = Column(String, nullable=True, unique=True)
    artwork_path = Column(String, nullable=True)

    playlist_tracks = relationship(
        "PlaylistTrack",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistTrack.position",
    )