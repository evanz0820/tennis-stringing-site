"""Application settings.

Everything configurable lives here and is read from the environment so the same
image runs in dev (SQLite) and prod (Postgres via DATABASE_URL). Import the
module-level ``settings`` singleton; do not read os.environ elsewhere.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ------------------------------------------------------------
    # SQLite in dev; set DATABASE_URL to a Postgres URL in prod.
    DATABASE_URL: str = "sqlite:///./dev.db"

    # --- Auth ----------------------------------------------------------------
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Public sign-up only ever creates customers. Creating a stringer account
    # requires this secret code, so only the owner (who sets it) can become the
    # stringer. Empty ("") disables stringer sign-up entirely.
    STRINGER_SIGNUP_CODE: str = ""

    # --- Email (Resend) ------------------------------------------------------
    # Set RESEND_API_KEY to enable sending. If empty, email is disabled and
    # messages are logged instead (so dev/tests never block on email).
    # EMAIL_FROM must be from a domain you've verified in Resend; the
    # onboarding@resend.dev default only delivers to your own Resend account
    # email (fine for testing).
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Strings by Evan <onboarding@resend.dev>"
    VERIFICATION_TTL_MINUTES: int = 15

    # Public URL of the app, used in email links.
    APP_BASE_URL: str = "http://localhost:5173"

    # --- Shop hours ----------------------------------------------------------
    # Open-hours slot grid. dropoff_at is validated against these (Task 2) but
    # there is no capacity or booking: any number of jobs may share a slot.
    OPEN_TIME: str = "09:00"   # HH:MM, naive local
    CLOSE_TIME: str = "18:00"  # HH:MM, naive local
    SLOT_MINUTES: int = 30

    # --- Display -------------------------------------------------------------
    # Informational only. Shown to customers; not a promise or a scheduling rule.
    TURNAROUND_NOTE: str = (
        "Most racquets are ready within a day, depending on the current queue."
    )

    # Physical drop-off address. Deliberately NOT served by the public /info
    # endpoint: it is only returned on the job-creation response, and only when
    # the customer actually set a drop-off time — so casual browsers never see it.
    DROP_OFF_ADDRESS: str = "123 Court Lane, Atlanta, GA 30303"

    # --- Misc ----------------------------------------------------------------
    # Guard for dev convenience only; prod relies on `alembic upgrade head`.
    CREATE_ALL_ON_STARTUP: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
