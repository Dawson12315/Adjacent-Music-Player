from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String

from app.db import Base


class TrackAudioProfile(Base):
    """What a track sounds like, as numbers: the raw features
    `services/audio_features.py` measured (tempo, loudness, brightness,
    timbre, harmony). Raw rather than standardised, so the map can be
    re-standardised over the whole library on every rebuild without
    listening again. Derived data: rebuilt by analysis, never edited.
    """

    __tablename__ = "track_audio_profiles"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    # Bumped when the feature list changes; older rows are measured again.
    version = Column(Integer, nullable=False)
    features = Column(LargeBinary, nullable=False)  # float32, FEATURE_NAMES order
    feature_count = Column(Integer, nullable=False)
    built_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TrackFeatureVector(Base):
    """A track's position in one of the map's extra blocks: `kind` is
    "sound" (from the audio profile) or "words" (from the lyrics). Unit
    float32 rows, rebuilt with the map; a track with no row in a block is
    simply unplaced there, which scores as neutral.
    """

    __tablename__ = "track_feature_vectors"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    kind = Column(String, primary_key=True)
    vector = Column(LargeBinary, nullable=False)
    dim = Column(Integer, nullable=False)
    built_at = Column(DateTime, nullable=False, default=datetime.utcnow)
