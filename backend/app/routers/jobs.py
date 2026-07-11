"""Stringing job endpoints.

GET /jobs returns every job (with customer info) to a stringer, and only the
caller's own jobs to a customer. The stringer's live queue (Task 4) is built
entirely on the client from this one endpoint; no queue-specific route is needed.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import schemas
from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..email import try_send
from ..models import JOB_STATUSES, StringingJob, User
from ..scheduling import dropoff_error, slot_error

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _validate_dropoff(value):
    """Raise 422 with a clear message if the drop-off time is invalid (Task 2)."""
    error = dropoff_error(value)
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)


def _validate_pickup(value):
    error = slot_error(value, label="Pickup time")
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)


def _fmt(dt) -> str:
    return dt.strftime("%a %b %-d at %-I:%M %p") if dt else "a flexible time"


def _notify_ready(job: StringingJob) -> None:
    """Email the customer that their racquet is ready for pickup."""
    try_send(
        job.customer.email,
        "Your racquet is ready for pickup 🎾 — Strings by Evan",
        f"Hi {job.customer.name},\n\n"
        f"Good news — your {job.racquet} is freshly strung and ready for pickup!\n\n"
        f"Please log in and confirm when you'll come by: {settings.APP_BASE_URL}\n\n"
        "Thanks,\nStrings by Evan",
    )


def _notify_pickup_scheduled(job: StringingJob, db: Session) -> None:
    """Email every stringer that the customer confirmed a pickup time."""
    for stringer in db.query(User).filter(User.role == "stringer").all():
        try_send(
            stringer.email,
            f"Pickup scheduled: {job.customer.name} — {job.racquet}",
            f"{job.customer.name} will pick up their {job.racquet} "
            f"({_fmt(job.pickup_eta)}).",
        )


@router.post("", response_model=schemas.JobCreatedOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: schemas.JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can request jobs")

    _validate_dropoff(payload.dropoff_at)

    job = StringingJob(
        customer_id=user.id,
        racquet=payload.racquet,
        string_preference=payload.string_preference,
        tension=payload.tension,
        notes=payload.notes,
        dropoff_at=payload.dropoff_at,
        status="requested",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    result = schemas.JobCreatedOut.model_validate(job)
    # Only reveal the drop-off address once the customer commits to a time.
    if job.dropoff_at is not None:
        result.dropoff_address = settings.DROP_OFF_ADDRESS
    return result


@router.get("", response_model=list[schemas.JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(StringingJob).options(joinedload(StringingJob.customer))
    if user.role != "stringer":
        query = query.filter(StringingJob.customer_id == user.id)
    return query.order_by(StringingJob.created_at.desc()).all()


@router.patch("/{job_id}", response_model=schemas.JobOut)
def update_job(
    job_id: int,
    payload: schemas.JobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.get(StringingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    is_stringer = user.role == "stringer"
    if not is_stringer and job.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    data = payload.model_dump(exclude_unset=True)
    prev_status = job.status
    pickup_confirmed = False

    if "status" in data and data["status"] is not None:
        new_status = data["status"]
        if new_status not in JOB_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {JOB_STATUSES}")
        # Customers may only cancel; all other transitions are the stringer's.
        if not is_stringer and new_status != "cancelled":
            raise HTTPException(status_code=403, detail="Customers may only cancel a job")
        job.status = new_status

    if "dropoff_at" in data:
        # Reschedule (stringer) or customer adjusting their own drop-off time.
        _validate_dropoff(data["dropoff_at"])
        job.dropoff_at = data["dropoff_at"]

    if "pickup_eta" in data:
        # Customer (or stringer) confirming when they'll pick up a ready racquet.
        _validate_pickup(data["pickup_eta"])
        pickup_confirmed = data["pickup_eta"] is not None and data["pickup_eta"] != job.pickup_eta
        job.pickup_eta = data["pickup_eta"]

    if "string_preference" in data:
        job.string_preference = data["string_preference"]
    if "tension" in data:
        job.tension = data["tension"]
    if "notes" in data:
        job.notes = data["notes"]

    db.commit()
    db.refresh(job)

    # Side effects after the state is safely persisted. Email is best-effort and
    # never blocks or fails the update.
    if job.status == "completed" and prev_status != "completed":
        _notify_ready(job)
    if pickup_confirmed:
        _notify_pickup_scheduled(job, db)

    return job
