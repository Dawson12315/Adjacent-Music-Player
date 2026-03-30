from typing import Optional

from pydantic import BaseModel


class AppSettingsResponse(BaseModel):
    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None


class AppSettingsUpdate(BaseModel):
    cleanup_enabled: bool
    cleanup_time: Optional[str] = None
    scan_enabled: bool
    scan_time: Optional[str] = None