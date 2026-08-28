from app.config import Settings


def test_vote_python_weekday_default_is_thursday():
    # VOTE_WEEKDAY uses 0=Sunday...6=Saturday; Python's date.weekday() uses 0=Monday...6=Sunday.
    assert Settings(vote_weekday=4).vote_python_weekday == 3


def test_vote_python_weekday_sunday():
    assert Settings(vote_weekday=0).vote_python_weekday == 6


def test_vote_python_weekday_saturday():
    assert Settings(vote_weekday=6).vote_python_weekday == 5
