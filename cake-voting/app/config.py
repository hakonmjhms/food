from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_base_url: str = "http://localhost:8000"

    # Session cookie signing key (used only for the CSRF token, since there's no login)
    session_secret_key: str = "dev-insecure-secret-change-me"

    # Database connection string (SQLite by default for local dev)
    database_url: str = "sqlite:///./cake_voting.db"

    # Which weekday the vote runs on: 0=Sunday, 1=Monday, ..., 6=Saturday. Default is 4 (Thursday).
    vote_weekday: int = Field(default=4, ge=0, le=6)

    @property
    def vote_python_weekday(self) -> int:
        """`vote_weekday` (0=Sunday...6=Saturday) converted to Python's date.weekday() convention (0=Monday...6=Sunday)."""
        return (self.vote_weekday + 6) % 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
