from sqlalchemy import Boolean, Column, Integer, String

from app.db import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    cleanup_enabled = Column(Boolean, nullable=False, default=False)
    cleanup_time = Column(String, nullable=True)
    scan_enabled = Column(Boolean, nullable=False, default=False)
    scan_time = Column(String, nullable=True)
    lastfm_api_key = Column(String, nullable=True)
    lastfm_api_secret = Column(String, nullable=True)
    lastfm_username = Column(String, nullable=True)
    lastfm_session_key = Column(String, nullable=True)