"""decisions table."""

from __future__ import annotations

from typing import Any

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    project_id: int | None,
    title: str,
    context: str | None,
    decision: str,
) -> Row:
    values: dict[str, Any] = {"title": title, "decision": decision}
    if project_id is not None:
        values["project_id"] = project_id
    if context is not None:
        values["context"] = context
    return _sql.insert(conn, "decisions", values)


def list_(conn: Conn, *, project_id: int | None) -> list[Row]:
    where = {"project_id": project_id} if project_id is not None else None
    return _sql.select(conn, "decisions", where=where)
