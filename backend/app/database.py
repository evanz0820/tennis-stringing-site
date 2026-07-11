"""SQLAlchemy engine/session wiring.

The DATABASE_URL normalization here is the single source of truth for how a
``postgres://`` URL is rewritten to ``postgresql://`` (Heroku-style URLs). Alembic
imports :func:`normalized_database_url` so migrations and the app agree.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


def normalized_database_url(url: str) -> str:
    """Rewrite legacy ``postgres://`` URLs to the ``postgresql://`` driver name."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = normalized_database_url(settings.DATABASE_URL)

# check_same_thread is a SQLite-only flag; skip it for Postgres.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping avoids "server closed the connection unexpectedly" errors when a
# remote/serverless Postgres (Neon, Supabase) drops idle connections.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
