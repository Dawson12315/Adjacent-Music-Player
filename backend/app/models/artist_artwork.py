from sqlalchemy import Column, Integer, String

from app.db import Base


class ArtistArtwork(Base):
    __tablename__ = "artist_artwork"

    id = Column(Integer, primary_key=True, index=True)
    artist_name = Column(String, nullable=False)
    artist_key = Column(String, nullable=False, unique=True, index=True)
    artwork_path = Column(String, nullable=True)