"""Pydantic request/response models."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth --------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = "customer"
    # Required only when requesting the "stringer" role; ignored otherwise.
    stringer_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)


class ResendRequest(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    email_verified: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterResult(BaseModel):
    """Registration no longer logs the user in — they must verify first."""
    verification_required: bool = True
    email: EmailStr
    # Only populated when email sending is disabled (dev/local), so you can still
    # complete the flow without a real inbox. Never returned when SMTP is on.
    dev_code: str | None = None


# --- Jobs --------------------------------------------------------------------
# Requested string tension in lbs: whole numbers only, 40-60 inclusive.
# strict=True rejects non-integers (e.g. 52.5) with 422 rather than truncating.
# Required on create; optional on the partial update.
_TENSION = dict(ge=40, le=60, strict=True)


class JobCreate(BaseModel):
    racquet: str = Field(min_length=1, max_length=200)
    string_preference: str | None = Field(default=None, max_length=200)
    tension: int = Field(**_TENSION)  # required
    notes: str | None = None
    dropoff_at: datetime | None = None  # naive local; null = flexible


class JobUpdate(BaseModel):
    """Partial update. Stringers change status/reschedule; customers can cancel
    or adjust their own drop-off time."""
    status: str | None = None
    dropoff_at: datetime | None = None
    pickup_eta: datetime | None = None
    string_preference: str | None = Field(default=None, max_length=200)
    tension: int | None = Field(default=None, **_TENSION)
    notes: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    racquet: str
    string_preference: str | None
    tension: int | None
    notes: str | None
    status: str
    dropoff_at: datetime | None
    pickup_eta: datetime | None
    created_at: datetime
    updated_at: datetime
    customer: UserOut


class JobCreatedOut(JobOut):
    """Returned only from POST /jobs. Carries the drop-off address when the
    customer set a drop-off time; None otherwise (and never on the list endpoint)."""
    dropoff_address: str | None = None


# --- Info --------------------------------------------------------------------
class InfoOut(BaseModel):
    open_time: str
    close_time: str
    slot_minutes: int
    turnaround_note: str
