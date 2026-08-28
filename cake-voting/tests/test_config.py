import datetime as dt

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_vote_python_weekday_default_is_thursday():
    # VOTE_WEEKDAY uses 0=Sunday...6=Saturday; Python's date.weekday() uses 0=Monday...6=Sunday.
    assert Settings(vote_weekday=4).vote_python_weekday == 3


def test_vote_python_weekday_sunday():
    assert Settings(vote_weekday=0).vote_python_weekday == 6


def test_vote_python_weekday_saturday():
    assert Settings(vote_weekday=6).vote_python_weekday == 5


def test_military_time_fields_parse_to_time_objects():
    settings = Settings(
        vote_open_time=700, VOTE_CLOSE_TIME=1115, actual_vote_open_time=1135, actual_vote_close_time=1700
    )
    assert settings.vote_open_dt_time == dt.time(7, 0)
    assert settings.vote_cutoff_dt_time == dt.time(11, 15)
    assert settings.actual_vote_open_dt_time == dt.time(11, 35)
    assert settings.actual_vote_close_dt_time == dt.time(17, 0)


def test_invalid_military_time_is_rejected():
    with pytest.raises(ValidationError):
        Settings(VOTE_CLOSE_TIME=1160)  # minute 60 doesn't exist


def test_schedule_must_be_in_order():
    with pytest.raises(ValidationError):
        Settings(vote_open_time=1115, VOTE_CLOSE_TIME=700, actual_vote_open_time=1135)


def test_actual_vote_close_must_be_after_open():
    with pytest.raises(ValidationError):
        Settings(actual_vote_open_time=1135, actual_vote_close_time=1100)
