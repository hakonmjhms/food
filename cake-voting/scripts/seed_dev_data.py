"""Convenience script to populate a fresh local database with sample data.

Usage (from the cake-voting/ directory, with the venv active):
    python -m scripts.seed_dev_data
"""

import datetime as dt

from app.database import SessionLocal, init_db
from app.models import Cake, Week


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if not db.query(Cake).count():
            db.add_all(
                [
                    Cake(name="Chocolate cake"),
                    Cake(name="Carrot cake"),
                    Cake(name="Cheesecake"),
                    Cake(name="Vanilla cake"),
                ]
            )
            db.commit()
            print("Seeded sample cakes.")

        if not db.query(Week).count():
            today = dt.date.today()
            days_until_thursday = (3 - today.weekday()) % 7  # Thursday == 3
            thursday = today + dt.timedelta(days=days_until_thursday)
            db.add(
                Week(
                    event_date=thursday,
                    voting_opens_at=dt.datetime.combine(thursday, dt.time(7, 0)),
                    voting_closes_at=dt.datetime.combine(thursday, dt.time(11, 15)),
                    actual_vote_opens_at=dt.datetime.combine(thursday, dt.time(11, 35)),
                )
            )
            db.commit()
            print(f"Seeded a voting week for {thursday}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
