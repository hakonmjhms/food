from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import crud, stats
from ..config import get_settings
from ..database import get_db
from ..i18n import format_time_is, format_weekday_date_is, weekday_morning_phrase_is
from ..models import WeekStatus
from ..security import attach_voter_cookie, get_or_create_csrf_token, get_voter_token

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    voter_token = get_voter_token(request)
    week = crud.get_or_create_current_week(db)
    settings = get_settings()

    context = {
        "csrf_token": get_or_create_csrf_token(request),
        "week": week,
        "event_date_display": format_weekday_date_is(week.event_date),
        "vote_weekday_morning_phrase": weekday_morning_phrase_is(settings.vote_python_weekday),
        "vote_open_display": format_time_is(settings.vote_open_dt_time),
        "vote_cutoff_display": format_time_is(settings.vote_cutoff_dt_time),
        "actual_vote_open_display": format_time_is(settings.actual_vote_open_dt_time),
        "actual_vote_close_display": format_time_is(settings.actual_vote_close_dt_time),
        "status": week.effective_status().value,
        "is_open": week.effective_status() == WeekStatus.OPEN,
        "actual_vote_open": week.effective_status() == WeekStatus.REPORTING,
        "cakes": crud.get_active_cakes(db),
        "my_vote_cake_id": None,
        "my_actual_vote_cake_id": None,
        "results": stats.week_summary(db, week),
        "actual_results": None,
    }
    my_vote = crud.get_vote_by_token(db, week.id, voter_token)
    context["my_vote_cake_id"] = my_vote.cake_id if my_vote else None

    if week.effective_status() in (WeekStatus.REPORTING, WeekStatus.UNRESOLVED):
        actual_tallies, actual_total = stats.actual_cake_results(db, week)
        my_actual_vote = crud.get_actual_vote_by_token(db, week.id, voter_token)
        context.update(
            {
                "actual_results": {"tallies": actual_tallies, "total_votes": actual_total},
                "my_actual_vote_cake_id": my_actual_vote.cake_id if my_actual_vote else None,
            }
        )

    response = templates.TemplateResponse(request, "index.html", context)
    return attach_voter_cookie(response, voter_token)


@router.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Session = Depends(get_db)):
    voter_token = get_voter_token(request)
    weeks = crud.get_week_history(db)
    overview = stats.history_overview(db, weeks)
    week_summaries = [stats.week_summary(db, w) for w in weeks]
    personal = stats.personal_stats(db, voter_token)
    cake_stats = stats.cake_overview(db)
    response = templates.TemplateResponse(
        request,
        "history.html",
        {
            "overview": overview,
            "week_summaries": week_summaries,
            "personal": personal,
            "cake_stats": cake_stats,
        },
    )
    return attach_voter_cookie(response, voter_token)

