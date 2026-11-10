from sqlalchemy import Boolean, Column, Integer, String, false, true

from app.db import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    cleanup_enabled = Column(Boolean, nullable=False, default=False)
    cleanup_time = Column(String, nullable=True)
    scan_enabled = Column(Boolean, nullable=False, default=False)
    scan_time = Column(String, nullable=True)
    lastfm_enrichment_enabled = Column(Boolean, nullable=False, default=False)
    lastfm_enrichment_time = Column(String, nullable=True)
    lastfm_api_key = Column(String, nullable=True)
    lastfm_api_secret = Column(String, nullable=True)
    lastfm_username = Column(String, nullable=True)
    lastfm_session_key = Column(String, nullable=True)
    # Set once the existing playlists were turned newest-first (2 Nov 2026);
    # nullable so older installs gain the column at boot and the turn runs.
    playlists_newest_first = Column(Boolean, nullable=True)
    # Watch the music folder and import new files as they land (2 Nov 2026).
    # NOT NULL with a server default, so installs from before it gain the
    # column at boot without a rewrite.
    watch_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    # Produce lyrics on this server (timing for known words, words from the
    # audio) — an admin switch, off by default; the model and a nightly time.
    lyrics_generation_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    lyrics_model = Column(String, nullable=True)
    lyrics_time = Column(String, nullable=True)
    # Listen to the library for radio: sound profiles and vocal/language
    # flags (services/audio_analysis.py). On by default; cheap, local, and
    # the one thing the map cannot get from tags.
    audio_analysis_enabled = Column(Boolean, nullable=False, default=True, server_default=true())
    audio_analysis_time = Column(String, nullable=True)
