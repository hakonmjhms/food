"""
All datetimes in this app are naive and represent UTC. This keeps SQLite (used for
local dev) and PostgreSQL (used in production) behaving consistently without timezone
bookkeeping, which would be overkill for a small internal side project.
"""

import datetime as dt
import enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class WeekStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    OPEN = "open"
    CLOSED = "closed"  # prediction voting closed, actual-cake reporting not open yet
    REPORTING = "reporting"  # actual-cake reporting is open
    UNRESOLVED = "unresolved"  # reporting closed without the crowd reaching consensus
    REVEALED = "revealed"


class Cake(Base):
    __tablename__ = "cakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    votes: Mapped[list["Vote"]] = relationship(back_populates="cake", foreign_keys="Vote.cake_id")


class Week(Base):
    """A single Thursday voting event."""

    __tablename__ = "weeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_date: Mapped[dt.date] = mapped_column(Date, unique=True)
    voting_opens_at: Mapped[dt.datetime] = mapped_column(DateTime)
    voting_closes_at: Mapped[dt.datetime] = mapped_column(DateTime)
    actual_vote_opens_at: Mapped[dt.datetime] = mapped_column(DateTime)
    actual_vote_closes_at: Mapped[dt.datetime] = mapped_column(DateTime)
    actual_cake_id: Mapped[int | None] = mapped_column(ForeignKey("cakes.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    actual_cake: Mapped["Cake | None"] = relationship(foreign_keys=[actual_cake_id])
    votes: Mapped[list["Vote"]] = relationship(back_populates="week", cascade="all, delete-orphan")
    actual_cake_votes: Mapped[list["ActualCakeVote"]] = relationship(
        back_populates="week", cascade="all, delete-orphan"
    )

    def is_open(self, now: dt.datetime | None = None) -> bool:
        now = now or dt.datetime.utcnow()
        return self.voting_opens_at <= now <= self.voting_closes_at

    def effective_status(self, now: dt.datetime | None = None) -> WeekStatus:
        """Status is derived from dates/actual_cake rather than stored, to avoid drift."""
        if self.actual_cake_id is not None:
            return WeekStatus.REVEALED
        now = now or dt.datetime.utcnow()
        if now < self.voting_opens_at:
            return WeekStatus.UPCOMING
        if now <= self.voting_closes_at:
            return WeekStatus.OPEN
        if now < self.actual_vote_opens_at:
            return WeekStatus.CLOSED
        if now <= self.actual_vote_closes_at:
            return WeekStatus.REPORTING
        return WeekStatus.UNRESOLVED


class Vote(Base):
    """A single prediction. Votes are anonymous: `voter_token` is an opaque value
    from a browser cookie, not tied to any personal identity - it only exists to
    stop the same browser from voting twice in one week and to show "your" pick."""

    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("week_id", "voter_token", name="uq_one_vote_per_voter_per_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id"), index=True)
    voter_token: Mapped[str] = mapped_column(String(64), index=True)
    cake_id: Mapped[int] = mapped_column(ForeignKey("cakes.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    week: Mapped["Week"] = relationship(back_populates="votes")
    cake: Mapped["Cake"] = relationship(back_populates="votes", foreign_keys=[cake_id])


class ActualCakeVote(Base):
    """An anonymous report of what the actual cake was. There's no admin to record
    this manually - once one cake gets a strict majority with at least two reports,
    it's automatically locked in as the week's actual cake (see `crud.cast_actual_cake_vote`)."""

    __tablename__ = "actual_cake_votes"
    __table_args__ = (
        UniqueConstraint("week_id", "voter_token", name="uq_one_actual_vote_per_voter_per_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id"), index=True)
    voter_token: Mapped[str] = mapped_column(String(64), index=True)
    cake_id: Mapped[int] = mapped_column(ForeignKey("cakes.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    week: Mapped["Week"] = relationship(back_populates="actual_cake_votes")
    cake: Mapped["Cake"] = relationship(foreign_keys=[cake_id])
