import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import ActualCakeVote, Cake, Vote, Week

# An actual-cake report needs at least this many votes, and a strict majority of
# all reports so far, before it's automatically locked in (there's no admin to do it).
ACTUAL_CAKE_MIN_VOTES = 2

# The only cakes people can vote for - there's no admin, so this list is the single
# source of truth. Edit it here (and restart the app) to change the options.
DEFAULT_CAKE_NAMES = [
    "Súkkulaðikaka",
    "Gulrótarkaka",
    "Sjónvarpskaka",
    "Karamellukaka",
    "Hjónabandssæla",
    "Tiramisu",
    "Ostakaka",
    "Annað"
]


def get_active_cakes(db: Session) -> list[Cake]:
    return list(db.scalars(select(Cake).where(Cake.active.is_(True)).order_by(Cake.name)))


def get_all_cakes(db: Session) -> list[Cake]:
    return list(db.scalars(select(Cake).order_by(Cake.name)))


def create_cake(db: Session, name: str, photo_url: str | None = None) -> Cake:
    cake = Cake(name=name.strip(), photo_url=photo_url)
    db.add(cake)
    db.commit()
    db.refresh(cake)
    return cake


def ensure_default_cakes(db: Session) -> None:
    """Seed the hardcoded cake list on startup - idempotent, so it's safe to call every time."""
    existing_names = {cake.name for cake in get_all_cakes(db)}
    for name in DEFAULT_CAKE_NAMES:
        if name not in existing_names:
            db.add(Cake(name=name))
    db.commit()


def get_or_create_current_week(db: Session, now: dt.datetime | None = None) -> Week:
    """The upcoming/current week, auto-created for the next configured weekday if none exists.

    There's no admin to schedule weeks, so the app creates them itself on demand.
    The weekday and the open/cutoff/reporting times all come from settings
    (VOTE_WEEKDAY, VOTE_OPEN_TIME, VOTE_CUTOFF_TIME, ACTUAL_VOTE_OPEN_TIME, ACTUAL_VOTE_CLOSE_TIME).
    """
    now = now or dt.datetime.utcnow()
    today = now.date()
    settings = get_settings()
    week = db.scalar(select(Week).where(Week.event_date >= today).order_by(Week.event_date))
    if week is not None:
        _sync_upcoming_week_times(db, week, now, settings)
        return week

    days_until_target = (settings.vote_python_weekday - today.weekday()) % 7
    event_date = today + dt.timedelta(days=days_until_target)
    try:
        return create_week(
            db,
            event_date=event_date,
            voting_opens_at=dt.datetime.combine(event_date, settings.vote_open_dt_time),
            voting_closes_at=dt.datetime.combine(event_date, settings.vote_cutoff_dt_time),
            actual_vote_opens_at=dt.datetime.combine(event_date, settings.actual_vote_open_dt_time),
            actual_vote_closes_at=dt.datetime.combine(event_date, settings.actual_vote_close_dt_time),
        )
    except Exception:
        db.rollback()
        # A concurrent request may have created this week's row first.
        return db.scalar(select(Week).where(Week.event_date == event_date))


def _sync_upcoming_week_times(db: Session, week: Week, now: dt.datetime, settings) -> None:
    """Keep a week's not-yet-reached time boundaries in sync with the current
    schedule settings. Each boundary is synced independently, based on whether
    that specific boundary is still in the future - so e.g. changing the cutoff
    time still takes effect while voting is already open, but a boundary that's
    already passed is left alone rather than retroactively reshuffled."""
    changed = False
    for attr, configured_time in (
        ("voting_opens_at", settings.vote_open_dt_time),
        ("voting_closes_at", settings.vote_cutoff_dt_time),
        ("actual_vote_opens_at", settings.actual_vote_open_dt_time),
        ("actual_vote_closes_at", settings.actual_vote_close_dt_time),
    ):
        if now >= getattr(week, attr):
            continue
        new_value = dt.datetime.combine(week.event_date, configured_time)
        if getattr(week, attr) != new_value:
            setattr(week, attr, new_value)
            changed = True

    if changed:
        db.commit()
    db.commit()


def get_week_history(db: Session, limit: int = 52, now: dt.datetime | None = None) -> list[Week]:
    """Weeks that have already happened - excludes the upcoming/current week, which isn't history yet."""
    now = now or dt.datetime.utcnow()
    today = now.date()
    return list(
        db.scalars(select(Week).where(Week.event_date < today).order_by(Week.event_date.desc()).limit(limit))
    )


def create_week(
    db: Session,
    event_date: dt.date,
    voting_opens_at: dt.datetime,
    voting_closes_at: dt.datetime,
    actual_vote_opens_at: dt.datetime,
    actual_vote_closes_at: dt.datetime,
) -> Week:
    week = Week(
        event_date=event_date,
        voting_opens_at=voting_opens_at,
        voting_closes_at=voting_closes_at,
        actual_vote_opens_at=actual_vote_opens_at,
        actual_vote_closes_at=actual_vote_closes_at,
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
