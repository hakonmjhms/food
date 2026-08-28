from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite needs this flag to be usable from FastAPI's threaded request handling.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import crud, models  # noqa: F401  models imported for side effect: register on Base.metadata

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        crud.ensure_default_cakes(db)
    finally:
        db.close()
