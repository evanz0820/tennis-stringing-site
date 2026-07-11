"""Alembic environment.

The database URL is NOT taken from alembic.ini. Instead we read it from the
application config (DATABASE_URL) and reuse the app's normalization so migrations
and the running app always target the same database with the same driver name.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the app package importable when running `alembic` from backend/.
from app.database import Base, normalized_database_url  # noqa: E402
from app.config import settings  # noqa: E402
from app import models  # noqa: F401,E402  (register tables on Base.metadata)

config = context.config

# Inject the runtime DATABASE_URL (normalized) so alembic.ini stays free of secrets.
config.set_main_option("sqlalchemy.url", normalized_database_url(settings.DATABASE_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # render_as_batch keeps ALTER TABLE migrations working on SQLite.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
