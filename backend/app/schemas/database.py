from pydantic import BaseModel, Field


class DatabaseConnectionRequest(BaseModel):
    """Postgres connection details from the settings form.

    The password travels in exactly one direction: form → migration → the
    runtime config file. No response schema ever carries it back.
    """

    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=63)
    username: str = Field(min_length=1, max_length=63)
    password: str = Field(default="", max_length=512)

    # libpq sslmode; "prefer" tries TLS and falls back, which suits LAN installs.
    sslmode: str = Field(default="prefer", pattern="^(disable|prefer|require)$")
