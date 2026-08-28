import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db
from ..models import Week, WeekStatus
from ..security import (
    actual_vote_rate_limiter,
    attach_voter_cookie,
    get_voter_token,
    verify_csrf_token,
    vote_rate_limiter,
)

router = APIRouter(tags=["votes"])


@router.post("/vote")
def submit_vote(
    request: Request,
    week_id: int = Form(...),
    cake_id: int = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_csrf_token(request, csrf_token)
    voter_token = get_voter_token(request)
    vote_rate_limiter.check(voter_token)

    week = db.get(Week, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="Voting week not found")
    if week.effective_status(dt.datetime.utcnow()) != WeekStatus.OPEN:
        raise HTTPException(status_code=400, detail="Voting is closed for this week")

    active_cake_ids = {cake.id for cake in crud.get_active_cakes(db)}
    if cake_id not in active_cake_ids:
        raise HTTPException(status_code=400, detail="That cake isn't available for voting")

    crud.cast_vote(db, week, voter_token, cake_id)
    response = RedirectResponse("/", status_code=303)
    return attach_voter_cookie(response, voter_token)


@router.post("/actual-vote")
def submit_actual_vote(
    request: Request,
    week_id: int = Form(...),
    cake_id: int = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_csrf_token(request, csrf_token)
    voter_token = get_voter_token(request)
    actual_vote_rate_limiter.check(voter_token)

    week = db.get(Week, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="Voting week not found")
    if week.effective_status(dt.datetime.utcnow()) != WeekStatus.REPORTING:
        raise HTTPException(status_code=400, detail="Actual-cake reporting isn't open for this week")

    active_cake_ids = {cake.id for cake in crud.get_active_cakes(db)}
    if cake_id not in active_cake_ids:
        raise HTTPException(status_code=400, detail="That cake isn't available")

    crud.cast_actual_cake_vote(db, week, voter_token, cake_id)
    response = RedirectResponse("/", status_code=303)
    return attach_voter_cookie(response, voter_token)

