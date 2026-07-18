"""Migration fidelity and reversibility."""

from __future__ import annotations

import os

import psycopg
import pytest
from alembic import command

from emctl.alembic_cfg import make_config

EXPECTED_TABLES = {
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
}
EXPECTED_INDEXES = {
    "idx_tasks_status",
    "idx_runs_task",
    "idx_reviews_pr",
    "idx_debt_open",
    "idx_learnings_open",
    "idx_risks_open",
    "idx_task_events_task",
}


def _conn() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


def test_all_tables_present() -> None:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    names = {r[0] for r in rows}
    assert names >= EXPECTED_TABLES


def test_named_indexes_present() -> None:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        ).fetchall()
    names = {r[0] for r in rows}
    assert names >= EXPECTED_INDEXES


def test_check_constraint_rejects_invalid_value() -> None:
    conn = _conn()
    try:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO projects (name, repo, status) VALUES (%s, %s, %s)",
                ("bad-status", "r", "not-a-real-status"),
            )
    finally:
        conn.close()


def test_downgrade_then_upgrade_round_trips() -> None:
    cfg = make_config()
    command.downgrade(cfg, "base")
    with _conn() as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    remaining = {r[0] for r in rows}
    assert not (EXPECTED_TABLES & remaining)  # domain tables dropped
    command.upgrade(cfg, "head")
    with _conn() as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    assert {r[0] for r in rows} >= EXPECTED_TABLES


def test_partial_index_predicate() -> None:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            ("idx_tasks_status",),
        ).fetchall()
    assert rows
    assert "WHERE (status <> 'done'" in rows[0][0]


def _columns(conn: psycopg.Connection, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    ).fetchall()
    return {r[0] for r in rows}


def test_0003_single_step_round_trips() -> None:
    """0003's own downgrade/upgrade: the v2 tables and columns disappear at
    0002 and return at head. Restores head so later tests see the full schema."""
    cfg = make_config()
    command.downgrade(cfg, "0002")
    with _conn() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ).fetchall()
        }
        decision_cols = _columns(conn, "decisions")
        pr_cols = _columns(conn, "prs")
    assert "risks" not in tables
    assert "task_events" not in tables
    assert {"status", "significance", "superseded_by"} & decision_cols == set()
    assert "task_id" not in pr_cols

    command.upgrade(cfg, "head")
    with _conn() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ).fetchall()
        }
        decision_cols = _columns(conn, "decisions")
        pr_cols = _columns(conn, "prs")
    assert {"risks", "task_events"} <= tables
    assert {"status", "significance", "superseded_by"} <= decision_cols
    assert "task_id" in pr_cols


_RUN_TOKEN_COLUMNS = {
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
}


def test_0004_token_columns_present() -> None:
    with _conn() as conn:
        cols = _columns(conn, "runs")
    assert cols >= _RUN_TOKEN_COLUMNS
    assert "token_cost" in cols  # legacy lump left in place


def test_0004_single_step_round_trips() -> None:
    """0004's own downgrade/upgrade: the four typed token columns disappear at
    0003 and return at head. Restores head so later tests see the full schema."""
    cfg = make_config()
    command.downgrade(cfg, "0003")
    with _conn() as conn:
        cols = _columns(conn, "runs")
    assert _RUN_TOKEN_COLUMNS & cols == set()
    assert "token_cost" in cols  # downgrade must not touch the legacy column

    command.upgrade(cfg, "head")
    with _conn() as conn:
        cols = _columns(conn, "runs")
    assert cols >= _RUN_TOKEN_COLUMNS


def test_0003_backfill_seeds_synthetic_task_event() -> None:
    """The generic backfill seeds one `actor='backfill'` event per pre-existing
    task on upgrade — no hard-coded ids. Restores head at the end."""
    cfg = make_config()
    command.downgrade(cfg, "0002")  # drops task_events
    with _conn() as conn:
        conn.execute(
            "INSERT INTO projects (name, repo) VALUES ('bf', 'r')"
        )
        conn.execute(
            "INSERT INTO tasks (project_id, title, status) "
            "SELECT id, 'pre-existing', 'in_review' FROM projects WHERE name = 'bf'"
        )
        conn.commit()
    command.upgrade(cfg, "head")  # runs the backfill INSERT ... SELECT
    with _conn() as conn:
        rows = conn.execute(
            "SELECT to_status, from_status, actor FROM task_events"
        ).fetchall()
    assert rows == [("in_review", None, "backfill")]
