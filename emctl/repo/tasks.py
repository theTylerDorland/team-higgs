"""tasks table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def create(
    conn: Conn,
    *,
    project_id: int,
    title: str,
    spec: str | None,
    role: str | None,
    model_tier: str | None,
    prd_ref: str | None,
    status: str | None,
    branch: str | None,
    depends_on: list[int] | None,
) -> Row:
    values: dict[str, Any] = {"project_id": project_id, "title": title}
    optional = {
        "spec": spec,
        "role": role,
        "model_tier": model_tier,
        "prd_ref": prd_ref,
        "status": status,
        "branch": branch,
        "depends_on": depends_on,
    }
    for key, value in optional.items():
        if value is not None:
            values[key] = value
    return _sql.insert(conn, "tasks", values)


def get(conn: Conn, task_id: int) -> Row:
    return _sql.get(conn, "tasks", "task", task_id)


def update(conn: Conn, task_id: int, values: dict[str, Any]) -> Row:
    # Always advance updated_at; it takes no bound value.
    extra = [sql.SQL("updated_at = now()")]
    return _sql.update(conn, "tasks", "task", task_id, values, extra=extra)


def list_(
    conn: Conn,
    *,
    status: str | None,
    project_id: int | None,
    role: str | None,
    blocked: bool | None,
) -> list[Row]:
    where: dict[str, Any] = {}
    if status is not None:
        where["status"] = status
    if project_id is not None:
        where["project_id"] = project_id
    if role is not None:
        where["role"] = role
    if blocked is not None:
        where["blocked"] = blocked
    return _sql.select(conn, "tasks", where=where or None)
