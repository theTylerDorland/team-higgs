"""prs table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def open_(
    conn: Conn,
    *,
    project_id: int,
    github_pr: int,
    risk_level: str | None,
    em_summary: str | None,
    status: str | None,
    task_id: int | None,
) -> Row:
    values: dict[str, Any] = {"project_id": project_id, "github_pr": github_pr}
    if risk_level is not None:
        values["risk_level"] = risk_level
    if em_summary is not None:
        values["em_summary"] = em_summary
    if status is not None:
        values["status"] = status
    if task_id is not None:
        values["task_id"] = task_id
    return _sql.insert(conn, "prs", values)


def get(conn: Conn, pr_id: int) -> Row:
    return _sql.get(conn, "prs", "pr", pr_id)


def update(
    conn: Conn,
    pr_id: int,
    *,
    status: str | None,
    risk_level: str | None,
    em_summary: str | None,
    tyler_decision: str | None,
    task_id: int | None,
) -> Row:
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status
    if risk_level is not None:
        values["risk_level"] = risk_level
    if em_summary is not None:
        values["em_summary"] = em_summary
    if task_id is not None:
        values["task_id"] = task_id
    extra: list[Any] = []
    if tyler_decision is not None:
        values["tyler_decision"] = tyler_decision
        extra.append(sql.SQL("decided_at = now()"))
    return _sql.update(conn, "prs", "pr", pr_id, values, extra=extra or None)
