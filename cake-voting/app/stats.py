from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .i18n import format_date_is
from .models import ActualCakeVote, Cake, Vote, Week


@dataclass
class CakeTally:
    cake_id: int
    name: str
    votes: int
    percentage: float


def week_results(db: Session, week: Week) -> tuple[list[CakeTally], int]:
    rows = db.execute(
        select(Cake.id, Cake.name, func.count(Vote.id))
        .join(Vote, Vote.cake_id == Cake.id)
        .where(Vote.week_id == week.id)
        .group_by(Cake.id, Cake.name)
        .order_by(func.count(Vote.id).desc())
    ).all()
    total = sum(count for _, _, count in rows)
    tallies = [
        CakeTally(
            cake_id=cake_id,
            name=name,
            votes=count,
            percentage=round(count * 100 / total, 1) if total else 0.0,
        )
        for cake_id, name, count in rows
    ]
    return tallies, total


def actual_cake_results(db: Session, week: Week) -> tuple[list[CakeTally], int]:
    """Tally of anonymous reports for what the actual cake was, used to show
    progress towards the automatic consensus lock-in."""
    rows = db.execute(
        select(Cake.id, Cake.name, func.count(ActualCakeVote.id))
        .join(ActualCakeVote, ActualCakeVote.cake_id == Cake.id)
        .where(ActualCakeVote.week_id == week.id)
        .group_by(Cake.id, Cake.name)
        .order_by(func.count(ActualCakeVote.id).desc())
    ).all()
    total = sum(count for _, _, count in rows)
    tallies = [
        CakeTally(
            cake_id=cake_id,
            name=name,
            votes=count,
            percentage=round(count * 100 / total, 1) if total else 0.0,
        )
        for cake_id, name, count in rows
    ]
    return tallies, total


def week_summary(db: Session, week: Week) -> dict:
    tallies, total = week_results(db, week)
    top_pick = tallies[0] if tallies else None
    correctness = None
    if week.actual_cake_id is not None and total:
        correct_votes = next((t.votes for t in tallies if t.cake_id == week.actual_cake_id), 0)
        correctness = {
            "correct_votes": correct_votes,
            "correct_percentage": round(correct_votes * 100 / total, 1),
            "majority_was_correct": bool(top_pick and top_pick.cake_id == week.actual_cake_id),
        }
    return {
        "week": week,
        "event_date_display": format_date_is(week.event_date),
        "tallies": tallies,
        "total_votes": total,
        "top_pick": top_pick,
        "correctness": correctness,
    }


def history_overview(db: Session, weeks: list[Week]) -> dict:
    """Aggregate stats across all weeks. `weeks` must be ordered newest-first."""
    total_revealed = 0
    correct_weeks = 0
    total_votes_all = 0
    weeks_with_votes = 0
    cake_prediction_counts: dict[str, int] = {}
    actual_cake_counts: dict[str, int] = {}
    wrong_top_pick_counts: dict[str, int] = {}
    crowd_current_streak = 0
    streak_active = True  # stops counting once we pass a wrong or unrevealed week

    for week in weeks:
        tallies, total = week_results(db, week)
        total_votes_all += total
        if total:
            weeks_with_votes += 1
        for tally in tallies:
            cake_prediction_counts[tally.name] = cake_prediction_counts.get(tally.name, 0) + tally.votes

        if week.actual_cake_id is None:
            streak_active = False
            continue

        total_revealed += 1
        actual_cake_counts[week.actual_cake.name] = actual_cake_counts.get(week.actual_cake.name, 0) + 1
        top_pick = tallies[0] if tallies else None
        majority_correct = bool(top_pick and top_pick.cake_id == week.actual_cake_id)
        if majority_correct:
            correct_weeks += 1
            if streak_active:
                crowd_current_streak += 1
        else:
            streak_active = False
            if top_pick:
                wrong_top_pick_counts[top_pick.name] = wrong_top_pick_counts.get(top_pick.name, 0) + 1

    most_predicted = max(cake_prediction_counts.items(), key=lambda kv: kv[1], default=None)
    most_served = max(actual_cake_counts.items(), key=lambda kv: kv[1], default=None)
    most_often_wrong_guess = max(wrong_top_pick_counts.items(), key=lambda kv: kv[1], default=None)

    return {
        "weeks_tracked": len(weeks),
        "weeks_revealed": total_revealed,
        "total_votes": total_votes_all,
        "avg_votes_per_week": round(total_votes_all / weeks_with_votes, 1) if weeks_with_votes else None,
        "crowd_accuracy_percentage": round(correct_weeks * 100 / total_revealed, 1) if total_revealed else None,
        "crowd_current_streak": crowd_current_streak,
        "most_predicted_cake": most_predicted,
        "most_served_cake": most_served,
        "most_often_wrong_guess": most_often_wrong_guess,
    }


def cake_overview(db: Session) -> list[dict]:
    """Per-cake stats: how often each cake has been predicted, how often it's
    actually been served, and when it was last served - sorted by most predicted first."""
    cakes = db.scalars(select(Cake).order_by(Cake.name)).all()
    overview = []
    for cake in cakes:
        times_predicted = db.scalar(select(func.count(Vote.id)).where(Vote.cake_id == cake.id)) or 0
        times_served = db.scalar(select(func.count(Week.id)).where(Week.actual_cake_id == cake.id)) or 0
        last_served_date = db.scalar(select(func.max(Week.event_date)).where(Week.actual_cake_id == cake.id))
        overview.append(
            {
                "name": cake.name,
                "times_predicted": times_predicted,
                "times_served": times_served,
                "last_served_display": format_date_is(last_served_date) if last_served_date else None,
            }
        )
    overview.sort(key=lambda c: c["times_predicted"], reverse=True)
    return overview


def personal_stats(db: Session, voter_token: str) -> dict:
    votes = list(
        db.scalars(
            select(Vote).where(Vote.voter_token == voter_token).join(Week).order_by(Week.event_date.desc())
        )
    )
    revealed_votes = [v for v in votes if v.week.actual_cake_id is not None]
    correct = sum(1 for v in revealed_votes if v.cake_id == v.week.actual_cake_id)

    streak = 0
    for vote in revealed_votes:  # newest first
        if vote.cake_id == vote.week.actual_cake_id:
            streak += 1
        else:
            break

    return {
        "total_votes": len(votes),
        "revealed_votes": len(revealed_votes),
        "correct_votes": correct,
        "accuracy_percentage": round(correct * 100 / len(revealed_votes), 1) if revealed_votes else None,
        "current_streak": streak,
    }
