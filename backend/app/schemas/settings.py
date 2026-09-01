from typing import Optional

from pydantic import BaseModel


class AppSettingsResponse(BaseModel):
    """Secrets are write-only: the API reports whether they are configured,
    never their values. The api_key is not secret (Last.fm puts it in the
    user-facing auth URL) so it round-trips to prefill the settings form."""

    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None
    lastfm_enrichment_enabled: bool
    lastfm_enrichment_time: Optional[str] = None
    lastfm_api_key: Optional[str] = None
    lastfm_api_secret_set: bool = False
    lastfm_username: Optional[str] = None
    lastfm_session_key_set: bool = False


class AppSettingsUpdate(BaseModel):
    """lastfm_api_secret is keep-on-None: clients no longer receive the stored
    secret, so omitting it must not erase it. Send a new value to replace it or
    an empty string to clear it. The session key is only ever written by the
    server's own Last.fm session flow and cannot be set here."""

    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None
    lastfm_enrichment_enabled: bool = False
    lastfm_enrichment_time: Optional[str] = None
    lastfm_api_key: Optional[str] = None
    lastfm_api_secret: Optional[str] = None
    lastfm_username: Optional[str] = None