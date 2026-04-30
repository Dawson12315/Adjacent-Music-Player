from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    admin_exists: bool


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class AdminSetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user: UserResponse