"""Seed a stringer, a couple of customers, and some sample jobs.

Run after `alembic upgrade head`:

    python -m app.seed

Idempotent-ish: skips users that already exist by email.
"""
import os
from datetime import datetime, time, timedelta

from .auth import hash_password
from .database import DATABASE_URL, SessionLocal
from .models import StringingJob, User


def _next_day_at(hour: int, minute: int) -> datetime:
    """A future, on-grid, in-hours naive-local datetime for sample drop-offs."""
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    return datetime.combine(tomorrow, time(hour, minute))


def get_or_create_user(db, *, name, email, password, role) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        name=name, email=email, hashed_password=hash_password(password),
        role=role, email_verified=True,  # dev users skip the email step
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def run() -> None:
    # Safety: never drop demo data onto a real (non-SQLite) database like Neon
    # unless explicitly forced. This keeps test data off production.
    if not DATABASE_URL.startswith("sqlite") and os.getenv("SEED_ALLOW_REMOTE") != "true":
        print(
            "Refusing to seed a non-SQLite database "
            f"({DATABASE_URL.split('@')[-1][:40]}...). "
            "Set SEED_ALLOW_REMOTE=true to override."
        )
        return

    db = SessionLocal()
    try:
        get_or_create_user(
            db, name="Sam Stringer", email="stringer@example.com",
            password="password", role="stringer",
        )
        alice = get_or_create_user(
            db, name="Alice Ace", email="alice@example.com",
            password="password", role="customer",
        )
        bob = get_or_create_user(
            db, name="Bob Baseline", email="bob@example.com",
            password="password", role="customer",
        )

        if db.query(StringingJob).count() == 0:
            db.add_all([
                StringingJob(
                    customer_id=alice.id, racquet="Wilson Blade 98",
                    string_preference="Luxilon ALU Power 16L", tension=55,
                    dropoff_at=_next_day_at(10, 0), status="requested",
                ),
                StringingJob(
                    customer_id=bob.id, racquet="Babolat Pure Aero",
                    string_preference="RPM Blast 17", tension=50,
                    notes="Cracked grommet near throat.",
                    dropoff_at=_next_day_at(10, 30), status="received",
                ),
                StringingJob(
                    customer_id=alice.id, racquet="Yonex EZONE 100",
                    string_preference=None, tension=52,
                    dropoff_at=None, status="in_progress",
                ),
            ])
            db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
