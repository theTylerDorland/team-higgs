"""retros table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def open_(conn: Conn, *, trigger: str, doc_path: str | None) -> Row:
    values: dict[str, Any] = {"trigger": trigger}
    if doc_path is not None:
        values["doc_path"] = doc_path
    return _sql.insert(conn, "retros", values)


def close(conn: Conn, retro_id: int) -> Row:
    extra = [sql.SQL("closed_at = now()")]
    return _sql.update(conn, "retros", "retro", retro_id, {}, extra=extra)


def list_(conn: Conn) -> list[Row]:
    return _sql.select(conn, "retros")
