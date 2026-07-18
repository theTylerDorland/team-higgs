"""decisions table."""

from __future__ import annotations

from typing import Any

from emctl.db import Conn
from emctl.errors import ValidationError
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    project_id: int | None,
    title: str,
    context: str | None,
    decision: str,
    significance: str | None,
    status: str | None,
) -> Row:
    values: dict[str, Any] = {"title": title, "decision": decision}
    optional = {
        "project_id": project_id,
        "context": context,
        "significance": significance,
        "status": status,
    }
    for key, value in optional.items():
        if value is not None:
            values[key] = value
    return _sql.insert(conn, "decisions", values)


def supersede(conn: Conn, old_id: int, *, new_id: int) -> Row:
    """Mark ``old_id`` superseded by ``new_id`` (PRD §4).

    Sets OLD ``status='superseded'`` and ``superseded_by=new_id``. The FK on
    ``superseded_by`` rejects a non-existent ``new_id``; we also reject a
    self-supersession up front, and surface a clear not-found for the
    superseding decision before writing.
    """
    if old_id == new_id:
        raise ValidationError("a decision cannot supersede itself")
    _sql.get(conn, "decisions", "decision", new_id)
    return _sql.update(
        conn,
        "decisions",
        "decision",
        old_id,
        {"status": "superseded", "superseded_by": new_id},
    )


def list_(
    conn: Conn,
    *,
    project_id: int | None,
    significance: str | None,
    status: str | None,
) -> list[Row]:
    where: dict[str, Any] = {}
    if project_id is not None:
        where["project_id"] = project_id
    if significance is not None:
        where["significance"] = significance
    if status is not None:
        where["status"] = status
    return _sql.select(conn, "decisions", where=where or None)
