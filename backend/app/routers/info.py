"""Public shop info: open hours, slot size, and the turnaround note (Task 3)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..database import get_db
from ..models import ACTIVE_STATUSES, StringingJob
from ..racquets import RACQUETS

router = APIRouter(tags=["info"])


@router.get("/info", response_model=schemas.InfoOut)
def get_info():
    return schemas.InfoOut(
        open_time=settings.OPEN_TIME,
        close_time=settings.CLOSE_TIME,
        slot_minutes=settings.SLOT_MINUTES,
        turnaround_note=settings.TURNAROUND_NOTE,
    )


@router.get("/racquets", response_model=list[str])
def get_racquets():
    """Curated catalog for the request dropdown. Public; no auth needed."""
    return RACQUETS


@router.get("/queue", response_model=schemas.QueueOut)
def get_queue(db: Session = Depends(get_db)):
    """How many racquets are actively in the shop queue. Count only (no customer
    details), so it's public — shown on the hero page and to customers."""
    count = (
        db.query(StringingJob)
        .filter(StringingJob.status.in_(ACTIVE_STATUSES))
        .count()
    )
    return schemas.QueueOut(active_count=count)
