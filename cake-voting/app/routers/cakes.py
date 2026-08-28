from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db
from ..security import get_or_create_csrf_token, verify_csrf_token

router = APIRouter(prefix="/cakes", tags=["cakes"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
def list_cakes(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "cakes.html",
        {"csrf_token": get_or_create_csrf_token(request), "cakes": crud.get_all_cakes(db)},
    )


@router.post("")
def add_cake(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_csrf_token(request, csrf_token)
    try:
        crud.create_cake(db, name=name, description=description or None)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="That cake already exists")
    return RedirectResponse("/cakes", status_code=303)
