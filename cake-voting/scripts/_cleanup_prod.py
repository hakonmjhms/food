"""One-off cleanup: removes leftover smoke-test weeks/votes and stale English cake
names from the real database, now that cakes are hardcoded in Icelandic. Deleted
after running - not part of the app."""

from app.crud import DEFAULT_CAKE_NAMES
from app.database import SessionLocal
from app.models import Cake, Week

db = SessionLocal()
try:
    weeks = db.query(Week).all()
    week_count = len(weeks)
    for week in weeks:
        db.delete(week)
    db.commit()

    stale_cakes = db.query(Cake).filter(~Cake.name.in_(DEFAULT_CAKE_NAMES)).all()
    stale_names = [c.name for c in stale_cakes]
    for cake in stale_cakes:
        db.delete(cake)
    db.commit()

    print(f"Weeks removed: {week_count}")
    print(f"Stale cakes removed: {stale_names}")
    print(f"Remaining cakes: {[c.name for c in db.query(Cake).order_by(Cake.name).all()]}")
finally:
    db.close()
