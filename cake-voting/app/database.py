from sqlalchemy import create_engine, inspect, select, text
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
    _add_missing_columns()
    db = SessionLocal()
    try:
        crud.ensure_default_cakes(db)
    finally:
        db.close()


def _add_missing_columns() -> None:
    """`create_all()` only creates tables that don't exist yet - it never alters
    existing ones. Without a migration tool, a column added to a model later on
    would silently never appear on an already-deployed database, so patch it in
    here instead of letting every request against that table start failing."""
    import datetime as dt

    from .config import get_settings
    from .models import Week

    inspector = inspect(engine)
    if "weeks" not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns("weeks")}
    if "actual_vote_closes_at" in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE weeks ADD COLUMN actual_vote_closes_at TIMESTAMP"))

    # Backfill existing rows using the configured close time, same as new weeks get.
    close_time = get_settings().actual_vote_close_dt_time
    db = SessionLocal()
    try:
        for week in db.scalars(select(Week)):
            week.actual_vote_closes_at = dt.datetime.combine(week.event_date, close_time)
        db.commit()
    finally:
        db.close()
