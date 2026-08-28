import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import crud, stats
from app.database import Base
from app.models import ActualCakeVote, Cake, Vote, Week


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_week(db, event_date: dt.date) -> Week:
    now = dt.datetime.utcnow()
    week = Week(
        event_date=event_date,
        voting_opens_at=now - dt.timedelta(hours=2),
        voting_closes_at=now - dt.timedelta(hours=1),
        actual_vote_opens_at=now - dt.timedelta(minutes=30),
        actual_vote_closes_at=now + dt.timedelta(hours=1),
    )
    db.add(week)
    db.commit()
    db.refresh(week)
    return week


def test_one_vote_per_voter_per_week_is_enforced_by_the_database(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 1, 1))

    db.add(Vote(week_id=week.id, voter_token="voter-1", cake_id=cake_a.id))
    db.commit()

    db.add(Vote(week_id=week.id, voter_token="voter-1", cake_id=cake_b.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cast_vote_updates_existing_vote_instead_of_creating_a_second_one(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 1, 8))

    crud.cast_vote(db, week, "voter-1", cake_a.id)
    crud.cast_vote(db, week, "voter-1", cake_b.id)

    votes = db.query(Vote).filter_by(week_id=week.id, voter_token="voter-1").all()
    assert len(votes) == 1
    assert votes[0].cake_id == cake_b.id


def test_week_results_percentages(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 1, 15))

    voter_tokens = [f"voter-{i}" for i in range(4)]
    for i, voter_token in enumerate(voter_tokens):
        crud.cast_vote(db, week, voter_token, cake_a.id if i < 3 else cake_b.id)

    tallies, total = stats.week_results(db, week)
    assert total == 4
    assert tallies[0].name == "Chocolate"
    assert tallies[0].votes == 3
    assert tallies[0].percentage == 75.0


def test_actual_cake_locks_in_once_majority_and_min_votes_reached(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 1, 22))

    # A single vote is a "majority" but doesn't meet the minimum vote count yet.
    crud.cast_actual_cake_vote(db, week, "voter-1", cake_a.id)
    assert week.actual_cake_id is None

    # A second vote for a different cake means neither has a majority yet.
    crud.cast_actual_cake_vote(db, week, "voter-2", cake_b.id)
    assert week.actual_cake_id is None

    # A third vote gives Chocolate a strict majority (2 of 3) with enough votes.
    crud.cast_actual_cake_vote(db, week, "voter-3", cake_a.id)
    assert week.actual_cake_id == cake_a.id


def test_actual_cake_vote_is_one_per_voter_per_week(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 1, 29))

    crud.cast_actual_cake_vote(db, week, "voter-1", cake_a.id)
    crud.cast_actual_cake_vote(db, week, "voter-1", cake_b.id)

    reports = db.query(ActualCakeVote).filter_by(week_id=week.id, voter_token="voter-1").all()
    assert len(reports) == 1
    assert reports[0].cake_id == cake_b.id


class _FakeScheduleSettings:
    """Minimal stand-in for Settings, exposing only what _sync_week_times needs."""

    def __init__(self, open_time: dt.time, cutoff_time: dt.time, actual_open: dt.time, actual_close: dt.time):
        self.vote_open_dt_time = open_time
        self.vote_cutoff_dt_time = cutoff_time
        self.actual_vote_open_dt_time = actual_open
        self.actual_vote_close_dt_time = actual_close


def test_sync_week_times_picks_up_new_schedule_settings(db):
    event_date = dt.date(2026, 2, 12)
    week = Week(
        event_date=event_date,
        voting_opens_at=dt.datetime.combine(event_date, dt.time(7, 0)),
        voting_closes_at=dt.datetime.combine(event_date, dt.time(11, 15)),
        actual_vote_opens_at=dt.datetime.combine(event_date, dt.time(11, 35)),
        actual_vote_closes_at=dt.datetime.combine(event_date, dt.time(17, 0)),
    )
    db.add(week)
    db.commit()

    new_settings = _FakeScheduleSettings(dt.time(8, 0), dt.time(12, 0), dt.time(12, 15), dt.time(18, 0))
    crud._sync_week_times(db, week, new_settings)

    assert week.voting_opens_at == dt.datetime.combine(event_date, dt.time(8, 0))
    assert week.voting_closes_at == dt.datetime.combine(event_date, dt.time(12, 0))
    assert week.actual_vote_opens_at == dt.datetime.combine(event_date, dt.time(12, 15))
    assert week.actual_vote_closes_at == dt.datetime.combine(event_date, dt.time(18, 0))


def test_sync_week_times_updates_boundaries_even_after_they_have_passed(db):
    event_date = dt.date(2026, 2, 19)
    week = Week(
        event_date=event_date,
        voting_opens_at=dt.datetime.combine(event_date, dt.time(7, 0)),
        voting_closes_at=dt.datetime.combine(event_date, dt.time(11, 15)),
        actual_vote_opens_at=dt.datetime.combine(event_date, dt.time(11, 35)),
        actual_vote_closes_at=dt.datetime.combine(event_date, dt.time(17, 0)),
    )
    db.add(week)
    db.commit()

    # Even though "now" would be well past every one of these boundaries, this
    # is a test-only convenience, so all four still get updated regardless.
    new_settings = _FakeScheduleSettings(dt.time(8, 0), dt.time(12, 0), dt.time(12, 15), dt.time(18, 0))
    crud._sync_week_times(db, week, new_settings)

    assert week.voting_opens_at == dt.datetime.combine(event_date, dt.time(8, 0))
    assert week.voting_closes_at == dt.datetime.combine(event_date, dt.time(12, 0))
    assert week.actual_vote_opens_at == dt.datetime.combine(event_date, dt.time(12, 15))
    assert week.actual_vote_closes_at == dt.datetime.combine(event_date, dt.time(18, 0))


def test_cake_overview_tracks_predictions_and_last_served_date(db):
    cake_a = Cake(name="Chocolate")
    cake_b = Cake(name="Vanilla")
    db.add_all([cake_a, cake_b])
    db.commit()
    week = _make_week(db, dt.date(2026, 2, 5))

    crud.cast_vote(db, week, "voter-1", cake_a.id)
    crud.cast_vote(db, week, "voter-2", cake_a.id)
    crud.cast_vote(db, week, "voter-3", cake_b.id)
    crud.set_actual_cake(db, week, cake_a.id)

    overview = stats.cake_overview(db)
    by_name = {c["name"]: c for c in overview}

    assert by_name["Chocolate"]["times_predicted"] == 2
    assert by_name["Chocolate"]["times_served"] == 1
    assert by_name["Chocolate"]["last_served_display"] == "5. febrúar 2026"
    assert by_name["Vanilla"]["times_predicted"] == 1
    assert by_name["Vanilla"]["times_served"] == 0
    assert by_name["Vanilla"]["last_served_display"] is None
    # Sorted by most predicted first.
    assert overview[0]["name"] == "Chocolate"


