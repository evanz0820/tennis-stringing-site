"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, info, jobs

app = FastAPI(title="Tennis Stringing Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(info.router)


@app.get("/health", tags=["info"])
def health():
    return {"status": "ok"}


# Schema management is handled by Alembic (`alembic upgrade head`). We only
# create tables at startup when explicitly opted in via CREATE_ALL_ON_STARTUP,
# which is convenient for throwaway dev databases but off by default so prod
# never races the migrations.
if settings.CREATE_ALL_ON_STARTUP:  # pragma: no cover
    from .database import Base, engine
    from . import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
