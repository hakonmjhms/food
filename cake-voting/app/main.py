from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .database import init_db
from .routers import pages, votes

BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()
error_templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Cake Voting", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    same_site="lax",
    https_only=settings.app_base_url.startswith("https://"),
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(pages.router)
app.include_router(votes.router)


@app.exception_handler(FastAPIHTTPException)
async def html_aware_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return error_templates.TemplateResponse(
            request, "error.html", {"detail": exc.detail}, status_code=exc.status_code
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
