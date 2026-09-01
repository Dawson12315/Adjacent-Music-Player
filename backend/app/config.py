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

    # Whether the auth cookie carries the Secure flag. Self-hosted deployments
    # are usually plain HTTP on a LAN IP, where browsers refuse to send Secure
    # cookies at all — so this must be an explicit switch, not implied by
    # APP_ENV. Unset, it follows the environment (secure in production).
    # Set AUTH_COOKIE_SECURE=false for HTTP deployments, true behind TLS.
    auth_cookie_secure: bool | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("auth_cookie_secure", mode="before")
    @classmethod
    def _empty_cookie_secure_means_unset(cls, value):
        # Compose interpolation can hand us AUTH_COOKIE_SECURE="" — treat that
        # as "not configured" instead of failing bool validation at boot.
        if isinstance(value, str) and not value.strip():
            return None
        return value

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

    @property
    def cookie_secure(self) -> bool:
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return self.is_production


settings = Settings()