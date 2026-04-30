from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Spotify Replica API"
    app_env: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./data/app.db"
    music_library_path: str = "/music"
    frontend_origin: str = "http://localhost:5173"

    auth_secret_key: str = "CHANGE_ME"
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    auth_cookie_name: str = "adjacent_access_token"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()