"""projects table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError
from emctl.repo import _sql

Row = _sql.Row


def create(
    conn: Conn, *, name: str, repo: str, brief: str | None, status: str | None
) -> Row:
    values: dict[str, Any] = {"name": name, "repo": repo}
    if brief is not None:
        values["brief"] = brief
    if status is not None:
        values["status"] = status
    return _sql.insert(conn, "projects", values)


def get(conn: Conn, project_id: int) -> Row:
    return _sql.get(conn, "projects", "project", project_id)


def get_by_name(conn: Conn, name: str) -> Row:
    query = sql.SQL("SELECT * FROM projects WHERE name = %s")
    row = conn.execute(query, (name,)).fetchone()
    if row is None:
        raise NotFoundError(f"project '{name}' not found")
    return row


def get_by_ref(conn: Conn, ref: str) -> Row:
    """Resolve a project by integer id or unique name."""
    if ref.isdigit():
        return get(conn, int(ref))
    return get_by_name(conn, ref)


def list_(conn: Conn, *, status: str | None) -> list[Row]:
    where = {"status": status} if status is not None else None
    return _sql.select(conn, "projects", where=where)
