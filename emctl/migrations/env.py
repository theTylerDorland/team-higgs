"""Alembic environment.

Reads ``DATABASE_URL`` from the environment in both offline and online modes;
no URL is stored in ``alembic.ini``. Migrations are imperative (no autogenerate
/ model metadata), so ``target_metadata`` is ``None``.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from emctl.config import sqlalchemy_url

target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(sqlalchemy_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
