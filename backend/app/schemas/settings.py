from typing import Optional

from pydantic import BaseModel


class AppSettingsResponse(BaseModel):
    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None
    lastfm_enrichment_enabled: bool
    lastfm_enrichment_time: Optional[str] = None
    lastfm_api_key: Optional[str] = None
    lastfm_api_secret: Optional[str] = None
    lastfm_username: Optional[str] = None
    lastfm_session_key: Optional[str] = None


class AppSettingsUpdate(BaseModel):
    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None
    lastfm_enrichment_enabled: bool = False
    lastfm_enrichment_time: Optional[str] = None
    lastfm_api_key: Optional[str] = None
    lastfm_api_secret: Optional[str] = None
    lastfm_username: Optional[str] = None
    lastfm_session_key: Optional[str] = None