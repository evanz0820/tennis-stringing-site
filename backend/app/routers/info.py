"""Public shop info: open hours, slot size, and the turnaround note (Task 3)."""
from fastapi import APIRouter

from .. import schemas
from ..config import settings
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
