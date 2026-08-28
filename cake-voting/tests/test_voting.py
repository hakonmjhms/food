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

