from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None


class UserCreatedResponse(BaseModel):
    user: UserResponse
    # The one and only time the password exists in plaintext; only its bcrypt
    # hash is stored.
    temp_password: str


class TempPasswordResponse(BaseModel):
    temp_password: str
