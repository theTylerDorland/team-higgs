"""metric define/report, including the READ ONLY trust boundary."""

from __future__ import annotations

import os

import psycopg


def test_report_runs_stored_query(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke("project", "create", "--name", "a", "--repo", "r")
    invoke("project", "create", "--name", "b", "--repo", "r")
    invoke(
        "metric", "define", "--name", "project_count",
        "--query", "SELECT count(*) AS n FROM projects",
        "--rationale", "how big is the portfolio",
    )
    _, rows = invoke("metric", "report", "--name", "project_count")
    assert rows == [{"n": 2}]


def test_report_rejects_mutating_definition(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke(
        "metric", "define", "--name", "sneaky",
        "--query", "INSERT INTO retros (trigger) VALUES ('mutation')",
        "--rationale", "should never write",
    )
    result, _ = invoke("metric", "report", "--name", "sneaky")
    assert result.exit_code != 0
    # Confirm the READ ONLY transaction blocked the write entirely.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        count = conn.execute("SELECT count(*) FROM retros").fetchone()
    assert count is not None
    assert count[0] == 0


def test_report_unknown_metric_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("metric", "report", "--name", "does-not-exist")
    assert result.exit_code == 3
