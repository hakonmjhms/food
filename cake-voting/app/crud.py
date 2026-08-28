import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ActualCakeVote, Cake, Vote, Week

# An actual-cake report needs at least this many votes, and a strict majority of
# all reports so far, before it's automatically locked in (there's no admin to do it).
ACTUAL_CAKE_MIN_VOTES = 2



def get_active_cakes(db: Session) -> list[Cake]:
    return list(db.scalars(select(Cake).where(Cake.active.is_(True)).order_by(Cake.name)))


def get_all_cakes(db: Session) -> list[Cake]:
    return list(db.scalars(select(Cake).order_by(Cake.name)))


def create_cake(db: Session, name: str, description: str | None = None, photo_url: str | None = None) -> Cake:
    cake = Cake(name=name.strip(), description=description, photo_url=photo_url)
    db.add(cake)
    db.commit()
    db.refresh(cake)
    return cake


def get_or_create_current_week(db: Session, now: dt.datetime | None = None) -> Week:
    """The upcoming/current week, auto-created for the next Thursday if none exists.

    There's no admin to schedule weeks, so the app creates them itself on demand.
    Prediction voting runs 7:00-11:15 on the day, and actual-cake reporting opens
    at 11:35 (leaving a short gap after voting closes).
    """
    now = now or dt.datetime.utcnow()
    today = now.date()
    week = db.scalar(select(Week).where(Week.event_date >= today).order_by(Week.event_date))
    if week is not None:
        return week

    days_until_thursday = (3 - today.weekday()) % 7  # Thursday == 3
    event_date = today + dt.timedelta(days=days_until_thursday)
    try:
        return create_week(
            db,
            event_date=event_date,
            voting_opens_at=dt.datetime.combine(event_date, dt.time(7, 0)),
            voting_closes_at=dt.datetime.combine(event_date, dt.time(11, 15)),
            actual_vote_opens_at=dt.datetime.combine(event_date, dt.time(11, 35)),
        )
    except Exception:
        db.rollback()
        # A concurrent request may have created this week's row first.
        return db.scalar(select(Week).where(Week.event_date == event_date))


def get_week_history(db: Session, limit: int = 52) -> list[Week]:
    return list(db.scalars(select(Week).order_by(Week.event_date.desc()).limit(limit)))


def create_week(
    db: Session,
    event_date: dt.date,
    voting_opens_at: dt.datetime,
    voting_closes_at: dt.datetime,
    actual_vote_opens_at: dt.datetime,
) -> Week:
    week = Week(
        event_date=event_date,
        voting_opens_at=voting_opens_at,
        voting_closes_at=voting_closes_at,
        actual_vote_opens_at=actual_vote_opens_at,
    )
    db.add(week)
    db.commit()
    db.refresh(week)
    return week


def set_actual_cake(db: Session, week: Week, cake_id: int) -> Week:
    week.actual_cake_id = cake_id
    db.commit()
    db.refresh(week)
    return week


def get_vote_by_token(db: Session, week_id: int, voter_token: str) -> Vote | None:
    return db.scalar(select(Vote).where(Vote.week_id == week_id, Vote.voter_token == voter_token))


def cast_vote(db: Session, week: Week, voter_token: str, cake_id: int) -> Vote:
    """Create a vote, or update the existing one for this browser/week (one vote per
    voter per week, enforced at the database level via a unique constraint)."""
    existing = get_vote_by_token(db, week.id, voter_token)
    if existing is not None:
        existing.cake_id = cake_id
        db.commit()
        db.refresh(existing)
        return existing

    vote = Vote(week_id=week.id, voter_token=voter_token, cake_id=cake_id)
    db.add(vote)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Handle the rare race where a concurrent request inserted first.
        existing = get_vote_by_token(db, week.id, voter_token)
        if existing is None:
            raise
        existing.cake_id = cake_id
        db.commit()
        db.refresh(existing)
        return existing
    db.refresh(vote)
    return vote


def get_actual_vote_by_token(db: Session, week_id: int, voter_token: str) -> ActualCakeVote | None:
    return db.scalar(
        select(ActualCakeVote).where(ActualCakeVote.week_id == week_id, ActualCakeVote.voter_token == voter_token)
    )


def cast_actual_cake_vote(db: Session, week: Week, voter_token: str, cake_id: int) -> ActualCakeVote:
    """Record (or update) this browser's report of what the actual cake was, then
    lock it in for everyone once a cake reaches a strict majority with at least
    `ACTUAL_CAKE_MIN_VOTES` reports."""
    existing = get_actual_vote_by_token(db, week.id, voter_token)
    if existing is not None:
        existing.cake_id = cake_id
        db.commit()
        db.refresh(existing)
        vote = existing
    else:
        vote = ActualCakeVote(week_id=week.id, voter_token=voter_token, cake_id=cake_id)
        db.add(vote)
        try:
            db.commit()
        except Exception:
            db.rollback()
            existing = get_actual_vote_by_token(db, week.id, voter_token)
            if existing is None:
                raise
            existing.cake_id = cake_id
            db.commit()
            db.refresh(existing)
            vote = existing
        else:
            db.refresh(vote)

    _lock_in_actual_cake_if_consensus_reached(db, week)
    return vote


def _lock_in_actual_cake_if_consensus_reached(db: Session, week: Week) -> None:
    rows = db.execute(
        select(ActualCakeVote.cake_id, func.count(ActualCakeVote.id))
        .where(ActualCakeVote.week_id == week.id)
        .group_by(ActualCakeVote.cake_id)
    ).all()
    total = sum(count for _, count in rows)
    for cake_id, count in rows:
        if count >= ACTUAL_CAKE_MIN_VOTES and count * 2 > total:
            set_actual_cake(db, week, cake_id)
            return
