from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db

router = APIRouter(prefix="/cakes", tags=["cakes"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
def list_cakes(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "cakes.html", {"cakes": crud.get_active_cakes(db)})
