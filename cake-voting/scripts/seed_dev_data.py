"""Convenience script to populate a fresh local database with sample data.

Usage (from the cake-voting/ directory, with the venv active):
    python -m scripts.seed_dev_data
"""

from app import crud
from app.database import SessionLocal, init_db


def main() -> None:
    # init_db() already seeds the hardcoded cake list (crud.DEFAULT_CAKE_NAMES).
    init_db()
    db = SessionLocal()
    try:
        # Delegate to the app's own logic instead of duplicating it here, so the
        # seeded week always matches the current VOTE_* schedule settings.
        week = crud.get_or_create_current_week(db)
        print(f"Current voting week: {week.event_date}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

