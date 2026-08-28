import datetime as dt
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
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

    # Vote schedule, in military time (HHMM), e.g. 1100 for 11:00.
    vote_open_time: int = Field(default=700, ge=0, le=2359)
    vote_cutoff_time: int = Field(default=1115, ge=0, le=2359)
    actual_vote_open_time: int = Field(default=1135, ge=0, le=2359)
    actual_vote_close_time: int = Field(default=1700, ge=0, le=2359)

    @field_validator("vote_open_time", "vote_cutoff_time", "actual_vote_open_time", "actual_vote_close_time")
    @classmethod
    def _validate_military_time(cls, value: int) -> int:
        hours, minutes = divmod(value, 100)
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError(f"Invalid military time: {value:04d} (expected HHMM, e.g. 1100 for 11:00)")
        return value

    @model_validator(mode="after")
    def _validate_time_order(self) -> "Settings":
        if not (
            self.vote_open_time < self.vote_cutoff_time
            <= self.actual_vote_open_time < self.actual_vote_close_time
        ):
            raise ValueError(
                "Vote schedule must satisfy vote_open_time < vote_cutoff_time <= "
                "actual_vote_open_time < actual_vote_close_time"
            )
        return self

    @property
    def vote_python_weekday(self) -> int:
        """`vote_weekday` (0=Sunday...6=Saturday) converted to Python's date.weekday() convention (0=Monday...6=Sunday)."""
        return (self.vote_weekday + 6) % 7

    @property
    def vote_open_dt_time(self) -> dt.time:
        return self._to_time(self.vote_open_time)

    @property
    def vote_cutoff_dt_time(self) -> dt.time:
        return self._to_time(self.vote_cutoff_time)

    @property
    def actual_vote_open_dt_time(self) -> dt.time:
        return self._to_time(self.actual_vote_open_time)

    @property
    def actual_vote_close_dt_time(self) -> dt.time:
        return self._to_time(self.actual_vote_close_time)

    @staticmethod
    def _to_time(value: int) -> dt.time:
        hours, minutes = divmod(value, 100)
        return dt.time(hour=hours, minute=minutes)


@lru_cache
def get_settings() -> Settings:
    return Settings()

