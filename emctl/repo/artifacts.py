"""artifacts table."""

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
    task_id: int | None,
    type_: str,
    path: str,
) -> Row:
    values: dict[str, Any] = {
        "project_id": project_id,
        "type": type_,
        "path": path,
    }
    if task_id is not None:
        values["task_id"] = task_id
    return _sql.insert(conn, "artifacts", values)


def decide(
    conn: Conn, artifact_id: int, *, status: str, notes: str | None
) -> Row:
    values: dict[str, Any] = {"status": status}
    if notes is not None:
        values["notes"] = notes
    extra = [sql.SQL("decided_at = now()")]
    return _sql.update(
        conn, "artifacts", "artifact", artifact_id, values, extra=extra
    )


def list_(
    conn: Conn,
    *,
    project_id: int | None,
    task_id: int | None,
    type_: str | None,
) -> list[Row]:
    where: dict[str, Any] = {}
    if project_id is not None:
        where["project_id"] = project_id
    if task_id is not None:
        where["task_id"] = task_id
    if type_ is not None:
        where["type"] = type_
    return _sql.select(conn, "artifacts", where=where or None)
