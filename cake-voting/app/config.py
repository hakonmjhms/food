from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_base_url: str = "http://localhost:8000"

    # Session cookie signing key (used only for the CSRF token, since there's no login)
    session_secret_key: str = "dev-insecure-secret-change-me"

    # Database connection string (SQLite by default for local dev)
    database_url: str = "sqlite:///./cake_voting.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
