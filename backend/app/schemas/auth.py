from datetime import datetime

from pydantic import BaseModel, Field


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

    model_config = {
        "from_attributes": True,
    }

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