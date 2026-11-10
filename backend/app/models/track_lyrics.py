from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.db import Base


class TrackLyrics(Base):
    """The words of a track, and where they came from.

    One row per track. `source` says where the text came from and
    `synced_source` where the timing came from, because the two can differ:
    a file can carry plain lyrics whose timing the server then produced.

        embedded     a lyrics tag inside the file (USLT/SYLT, ©lyr, LYRICS)
        sidecar      a .lrc or .txt beside the file
        user         typed, pasted or corrected in Adjacent
        aligned      timing produced on this server for known text
        transcribed  text and timing produced on this server from the audio

    `synced` is JSON: a list of [seconds, line] pairs, in order. `plain` is
    the lyrics as text, one line per line, always present when `synced` is.
    """

    __tablename__ = "track_lyrics"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source = Column(String, nullable=False)
    synced_source = Column(String, nullable=True)
    plain = Column(Text, nullable=False)
    synced = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    # For generated rows: the model that produced them and how sure it was.
    model = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
