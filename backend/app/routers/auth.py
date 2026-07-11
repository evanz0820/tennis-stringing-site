"""Registration, email verification, and login."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import (
    create_access_token,
    generate_code,
    hash_code,
    hash_password,
    verification_expiry,
    verify_password,
)
from ..config import settings
from ..database import get_db
from ..email import email_enabled, try_send
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _resolve_role(payload: schemas.UserCreate) -> str:
    """Public sign-up is customer-only. The stringer role requires the secret
    STRINGER_SIGNUP_CODE, so only the owner can create a stringer account."""
    if payload.role == "stringer":
        expected = settings.STRINGER_SIGNUP_CODE
        provided = payload.stringer_code or ""
        # constant-time compare; also reject if no code is configured at all.
        if not expected or not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stringer sign-up is restricted.",
            )
        return "stringer"
    return "customer"


def _issue_code(user: User, db: Session) -> str:
    """Generate a fresh verification code, store its hash + expiry, email it."""
    code = generate_code()
    user.verification_code_hash = hash_code(code)
    user.verification_expires_at = verification_expiry()
    db.commit()
    try_send(
        user.email,
        "Verify your email — Strings by Evan",
        f"Hi {user.name},\n\n"
        f"Your verification code is: {code}\n\n"
        f"It expires in {settings.VERIFICATION_TTL_MINUTES} minutes.\n\n"
        "If you didn't sign up, you can ignore this email.",
    )
    return code


@router.post("/register", response_model=schemas.RegisterResult, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    role = _resolve_role(payload)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    code = _issue_code(user, db)
    # Expose the code only when email is off (dev/local) so the flow is testable.
    return schemas.RegisterResult(
        email=user.email,
        dev_code=None if email_enabled() else code,
    )


@router.post("/verify", response_model=schemas.Token)
def verify(payload: schemas.VerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or code")
    if user.email_verified:
        # Already verified — just log them in.
        return schemas.Token(access_token=create_access_token(str(user.id)), user=user)

    from datetime import datetime

    if (
        not user.verification_code_hash
        or not user.verification_expires_at
        or user.verification_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Code expired — request a new one.")
    if not secrets.compare_digest(hash_code(payload.code), user.verification_code_hash):
        raise HTTPException(status_code=400, detail="Invalid email or code")

    user.email_verified = True
    user.verification_code_hash = None
    user.verification_expires_at = None
    db.commit()
    db.refresh(user)
    return schemas.Token(access_token=create_access_token(str(user.id)), user=user)


@router.post("/resend", status_code=status.HTTP_202_ACCEPTED)
def resend(payload: schemas.ResendRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    # Don't reveal whether the email exists / is already verified.
    if not user or user.email_verified:
        return {"ok": True}
    code = _issue_code(user, db)
    return {"ok": True, "dev_code": None if email_enabled() else code}


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.email_verified:
        # 403 with a stable detail so the frontend can route to the verify step.
        raise HTTPException(status_code=403, detail="Email not verified")
    return schemas.Token(access_token=create_access_token(str(user.id)), user=user)
