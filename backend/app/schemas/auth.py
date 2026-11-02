from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.themes import DEFAULT_THEME, is_theme


class SetupStatusResponse(BaseModel):
    admin_exists: bool
    # True when the server requires a SETUP_TOKEN to create the first admin,
    # so the setup screen knows to ask for one. Never echoes the token itself.
    setup_token_required: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool = False
    created_at: datetime | None = None
    # The IANA zone chosen in Settings, or null for "this device's".
    timezone: str | None = None
    # The look the account wears on every device: one of the server's theme
    # ids, Adjacent by default; whether the seasons may take over from it;
    # and whether the seasons run as in the southern hemisphere.
    theme: str = DEFAULT_THEME
    theme_seasonal: bool = False
    theme_southern: bool = False

    model_config = {
        "from_attributes": True,
    }

    @field_validator("theme", mode="before")
    @classmethod
    def _theme_or_default(cls, value):
        return value if is_theme(value) else DEFAULT_THEME

    @field_validator("theme_seasonal", "theme_southern", mode="before")
    @classmethod
    def _flag_or_false(cls, value):
        return bool(value)


class PreferencesUpdateRequest(BaseModel):
    """Settings that are not credentials and need no password to change.

    Only the fields sent are changed: a client saving a theme does not touch
    the time zone, and the other way round.
    """

    # An IANA name, or null to go back to following the device.
    timezone: str | None = Field(default=None, max_length=64)
    # A theme id from services/themes.py; null means Adjacent.
    theme: str | None = Field(default=None, max_length=32)
    theme_seasonal: bool | None = None
    theme_southern: bool | None = None

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, value):
        if value is None:
            return None
        if not is_theme(value):
            raise ValueError(f"Unknown theme: {value}")
        return value

class StreamTokenResponse(BaseModel):
    token: str
    
class AdminSetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    # Only consulted when the server has SETUP_TOKEN configured; installs
    # without it never send or need this.
    setup_token: str | None = Field(default=None, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user: UserResponse


class AccountUpdateRequest(BaseModel):
    current_password: str
    username: str | None = Field(default=None, min_length=3, max_length=50)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    confirm_password: str | None = Field(default=None, min_length=8, max_length=128)

class PasswordRecoveryRequest(BaseModel):
    username: str
    recovery_code: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]