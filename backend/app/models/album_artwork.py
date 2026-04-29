from sqlalchemy import Column, Integer, String

from app.db import Base


class AlbumArtwork(Base):
    __tablename__ = "album_artwork"

    id = Column(Integer, primary_key=True, index=True)
    album_name = Column(String, nullable=False)
    album_key = Column(String, nullable=False, unique=True, index=True)
    artwork_path = Column(String, nullable=True)