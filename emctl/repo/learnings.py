"""learnings table."""

from __future__ import annotations

from typing import Any

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    category: str,
    observation: str,
    evidence: str | None,
    filed_by: str | None,
) -> Row:
    values: dict[str, Any] = {"category": category, "observation": observation}
    if evidence is not None:
        values["evidence"] = evidence
    if filed_by is not None:
        values["filed_by"] = filed_by
    return _sql.insert(conn, "learnings", values)


def resolve(conn: Conn, learning_id: int, *, retro_id: int) -> Row:
    return _sql.update(
        conn,
        "learnings",
        "learning",
        learning_id,
        {"status": "resolved", "retro_id": retro_id},
    )


def list_(
    conn: Conn, *, category: str | None, status: str | None
) -> list[Row]:
    where: dict[str, Any] = {}
    if category is not None:
        where["category"] = category
    if status is not None:
        where["status"] = status
    return _sql.select(conn, "learnings", where=where or None)
