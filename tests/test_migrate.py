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
}
EXPECTED_INDEXES = {
    "idx_tasks_status",
    "idx_runs_task",
    "idx_reviews_pr",
    "idx_debt_open",
    "idx_learnings_open",
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
