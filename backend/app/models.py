"""ORM models. Table names are explicit so migrations stay stable."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Job lifecycle. Kept as plain strings (not a DB enum) to match the lightweight
# style of the rest of the app and keep migrations simple across SQLite/Postgres.
JOB_STATUSES = (
    "requested",
    "received",
    "in_progress",
    "completed",
    "picked_up",
    "cancelled",
)

# Jobs a stringer still has to act on. Used by the frontend queue (Task 4).
ACTIVE_STATUSES = ("requested", "received", "in_progress")

ROLES = ("customer", "stringer")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")

    jobs: Mapped[list["StringingJob"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class StringingJob(Base):
    __tablename__ = "stringing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    racquet: Mapped[str] = mapped_column(String(200), nullable=False)
    string_preference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Requested string tension in lbs. Optional; validated to 40-60 at the API.
    tension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")

    # Naive local datetime: when the customer plans to hand off the racquet.
    # NOT an appointment slot; null means "flexible". No capacity/booking.
    dropoff_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    customer: Mapped["User"] = relationship(back_populates="jobs")
