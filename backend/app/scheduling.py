"""Drop-off time validation (Task 2).

Input validation only. We check exactly two things and nothing else:

1. dropoff_at is not in the past.
2. dropoff_at lands on an open-hours slot boundary derived from the settings
   (OPEN_TIME, CLOSE_TIME, SLOT_MINUTES).

We deliberately do NOT look at other jobs, capacity, or availability: drop-off
time is not an appointment and any number of jobs may share the same time.
A null dropoff_at ("flexible") is always allowed.
"""
from datetime import date, datetime, time, timedelta

from .config import Settings, settings as default_settings


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def open_slots(settings: Settings) -> list[time]:
    """The valid time-of-day slot boundaries, inclusive of open and close."""
    start = _parse_hhmm(settings.OPEN_TIME)
    end = _parse_hhmm(settings.CLOSE_TIME)
    step = timedelta(minutes=settings.SLOT_MINUTES)

    slots: list[time] = []
    cur = datetime.combine(date.min, start)
    end_dt = datetime.combine(date.min, end)
    while cur <= end_dt:
        slots.append(cur.time())
        cur += step
    return slots


def slot_error(
    value: datetime | None,
    settings: Settings | None = None,
    now: datetime | None = None,
    label: str = "Time",
) -> str | None:
    """Return a human-readable error for an invalid slot datetime, else None.

    Validates the same two rules used for drop-off and pickup: not in the past,
    and on an open-hours slot boundary. ``now`` is injectable for testing;
    defaults to naive local now to match the naive-local semantics of the field.
    """
    if value is None:
        return None

    settings = settings or default_settings
    now = now or datetime.now()

    if value < now:
        return f"{label} cannot be in the past."

    valid = open_slots(settings)
    if value.time() not in set(valid):
        pretty = f"{settings.OPEN_TIME}-{settings.CLOSE_TIME}"
        return (
            f"{label} must fall on a {settings.SLOT_MINUTES}-minute slot "
            f"boundary within open hours ({pretty})."
        )
    return None


def dropoff_error(value, settings=None, now=None):
    return slot_error(value, settings, now, label="Drop-off time")
