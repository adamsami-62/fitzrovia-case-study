"""Initialize the database schema and seed known buildings + users."""
import os
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import Base, engine, SessionLocal
from backend.app.models import Building, User


# Note: bcrypt password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


BUILDINGS = [
    {"name": "Parker",
     "address": "200 Redpath Avenue, Toronto",
     "scraper_key": "parker"},

    # Story of Midtown — split into two buildings (different addresses, different price points)
    {"name": "Story of Midtown (73 Broadway - New)",
     "address": "73 Broadway Avenue, Toronto",
     "scraper_key": "story_of_midtown_73"},
    {"name": "Story of Midtown (75 Broadway - Revitalized)",
     "address": "75 Broadway Avenue, Toronto",
     "scraper_key": "story_of_midtown_75"},

    {"name": "The Selby",
     "address": "25 Selby Street, Toronto",
     "scraper_key": "the_selby"},
    {"name": "eCentral",
     "address": "15 Roehampton Avenue, Toronto",
     "scraper_key": "ecentral"},
    {"name": "The Montgomery",
     "address": "2388 Yonge Street, Toronto",
     "scraper_key": "the_montgomery"},
    {"name": "The Whitney",
     "address": "71 Redpath Avenue, Toronto",
     "scraper_key": "the_whitney"},
    {"name": "The Hampton",
     "address": "101 Roehampton Avenue, Toronto",
     "scraper_key": "the_hampton"},
    {"name": "E18HTEEN",
     "address": "18 Erskine Avenue, Toronto",
     "scraper_key": "e18hteen"},
    {"name": "Corner on Broadway",
     "address": "223 Redpath Avenue, Toronto",
     "scraper_key": "corner_on_broadway"},
    {"name": "Akoya Living",
     "address": "55 Broadway Avenue, Toronto",
     "scraper_key": "akoya_living"},
]


def seed_users(db: Session) -> int:
    created = 0
    for email, pw, role in [
        (settings.admin_email, settings.admin_password, "admin"),
        (settings.viewer_email, settings.viewer_password, "viewer"),
    ]:
        if db.query(User).filter_by(email=email).first() is None:
            db.add(User(
                email=email,
                password_hash=pwd_context.hash(pw),
                role=role,
            ))
            created += 1
    db.commit()
    return created


def seed_buildings(db: Session) -> int:
    created = 0
    for b in BUILDINGS:
        if db.query(Building).filter_by(scraper_key=b["scraper_key"]).first() is None:
            db.add(Building(**b))
            created += 1
    db.commit()
    return created


def main():
    os.makedirs("backend/data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print("\u2713 Tables created")

    db = SessionLocal()
    try:
        n_b = seed_buildings(db)
        print(f"\u2713 Seeded {n_b} buildings")
        n_u = seed_users(db)
        print(f"\u2713 Seeded {n_u} users")
    finally:
        db.close()


if __name__ == "__main__":
    main()
