"""migrate — apply Alembic migrations to head."""

from alembic import command

from emctl import output
from emctl.alembic_cfg import make_config
from emctl.config import database_url


def migrate_command() -> None:
    """Run `alembic upgrade head` against DATABASE_URL."""
    database_url()  # fail fast with ConfigError (exit 5) if unset
    command.upgrade(make_config(), "head")
    output.emit_record({"migrate": "ok", "revision": "head"})
