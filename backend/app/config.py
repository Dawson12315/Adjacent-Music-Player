from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Spotify Replica API"
    app_env: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./data/app.db"
    music_library_path: str = "/music"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()