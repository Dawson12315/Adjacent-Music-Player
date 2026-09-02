import json
import logging
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Written by the Postgres migration's cutover step, never by hand. It outranks
# DATABASE_URL so a migrated install keeps its database across restarts and
# image upgrades without anyone having to edit compose files. Deleting it
# falls the install back to whatever the environment says — that is the
# documented escape hatch if Postgres is ever unreachable.
RUNTIME_DATABASE_CONFIG_PATH = Path("data/database.json")

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

    # Optional shared secret for first-run admin creation. Unset (the default)
    # keeps the original behaviour: the first person to reach an admin-less
    # instance creates the admin. Set it before exposing a fresh install to the
    # internet, where that race is against scanners rather than housemates.
    setup_token: str | None = None

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


def load_runtime_database_url() -> str | None:
    try:
        raw = RUNTIME_DATABASE_CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        logger.warning(
            "Could not read %s (%s); using the configured DATABASE_URL",
            RUNTIME_DATABASE_CONFIG_PATH,
            error,
        )
        return None

    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning(
            "Ignoring malformed %s; using the configured DATABASE_URL",
            RUNTIME_DATABASE_CONFIG_PATH,
        )
        return None

    url = data.get("database_url")

    if isinstance(url, str) and url.strip():
        return url.strip()

    return None


settings = Settings()

_runtime_database_url = load_runtime_database_url()
if _runtime_database_url:
    settings.database_url = _runtime_database_url