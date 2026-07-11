"""Registration and login."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import create_access_token, hash_password, verify_password
from ..config import settings
from ..database import get_db
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


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    role = _resolve_role(payload)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return schemas.Token(access_token=create_access_token(str(user.id)), user=user)


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return schemas.Token(access_token=create_access_token(str(user.id)), user=user)
