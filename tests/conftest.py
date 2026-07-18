"""Test harness.

Points the application at ``DATABASE_URL_TEST`` (the app itself only ever reads
``DATABASE_URL``), runs the migrations once per session, and resets table state
between tests. Real Postgres — no mock DB.

Isolation note: each command opens and commits its own connection (correct
production behaviour), so a shared outer-transaction rollback would require
monkeypatching the app's connection management. Instead we TRUNCATE ... RESTART
IDENTITY between tests, which gives equivalent isolation without coupling the
tests to internals. (This is a deliberate departure from the PRD's stated
"per-test transaction rollback"; see the PR description.)
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from alembic import command
from psycopg import sql
from typer.testing import CliRunner

from emctl.alembic_cfg import make_config
from emctl.cli import app

TABLES = [
    "projects",
    "tasks",
    "runs",
    "prs",
    "reviews",
    "questions",
    "decisions",
    "artifacts",
    "learnings",
    "debt",
    "metrics",
    "retros",
    "risks",
    "task_events",
]


@pytest.fixture(scope="session", autouse=True)
def _migrated_db() -> Iterator[None]:
    test_url = os.environ.get("DATABASE_URL_TEST")
    if not test_url:
        pytest.skip("DATABASE_URL_TEST is not set")
    # The app reads only DATABASE_URL; point it at the throwaway test DB.
    os.environ["DATABASE_URL"] = test_url
    command.upgrade(make_config(), "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_db: None) -> Iterator[None]:
    yield
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        statement = sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
            sql.SQL(", ").join(sql.Identifier(t) for t in TABLES)
        )
        conn.execute(statement)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def invoke(runner: CliRunner):  # type: ignore[no-untyped-def]
    """Invoke emctl and, on success, return (result, parsed-json)."""

    def _invoke(*args: str, json_mode: bool = True) -> tuple[Any, Any]:
        argv = (["--json"] if json_mode else []) + list(args)
        result = runner.invoke(app, argv)
        parsed = None
        if json_mode and result.exit_code == 0 and result.output.strip():
            parsed = json.loads(result.output)
        return result, parsed

    return _invoke
