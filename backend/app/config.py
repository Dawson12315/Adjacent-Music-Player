from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder values that have shipped in examples or old defaults. Signing JWTs with
# any of these means anyone can forge an admin token, so refuse to boot with them.
_FORBIDDEN_SECRET_KEYS = {
    "CHANGE_ME",
    "make-this-a-long-random-secret",
}

_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "Adjacent API"
    app_env: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./data/app.db"
    music_library_path: str = "/music"
    frontend_origin: str = "http://localhost:5173"

    # No default on purpose: every deployment must supply its own signing key.
    auth_secret_key: str
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    auth_cookie_name: str = "adjacent_access_token"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("auth_secret_key")
    @classmethod
    def _require_real_secret_key(cls, value: str) -> str:
        if value in _FORBIDDEN_SECRET_KEYS or len(value) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                "AUTH_SECRET_KEY must be a random secret of at least "
                f"{_MIN_SECRET_KEY_LENGTH} characters. Generate one with: "
                "openssl rand -hex 32"
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()