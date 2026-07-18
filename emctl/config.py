"""Configuration from the environment.

The application reads exactly one connection string, ``DATABASE_URL``.
``DATABASE_URL_TEST`` exists only so the test harness can point the app at a
throwaway database; the application code never reads it. No connection
literals live in the codebase.
"""

from __future__ import annotations

import os

from emctl.errors import ConfigError


def database_url() -> str:
    """Return the required ``DATABASE_URL`` or raise :class:`ConfigError`."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ConfigError("DATABASE_URL is not set")
    return url


def sqlalchemy_url() -> str:
    """``DATABASE_URL`` rewritten to the SQLAlchemy + psycopg3 driver form.

    Alembic runs on SQLAlchemy, so its engine needs the ``postgresql+psycopg``
    dialect prefix. The underlying driver is still psycopg 3.
    """
    url = database_url()
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url
