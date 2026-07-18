"""task_events table (task status history).

Written by `task create`/`task update` on every status change so cycle-time and
rework metrics are computable (PRD §3-§4). Read by `task history`.
"""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    task_id: int,
    from_status: str | None,
    to_status: str,
    actor: str | None,
) -> Row:
    values: dict[str, Any] = {"task_id": task_id, "to_status": to_status}
    if from_status is not None:
        values["from_status"] = from_status
    if actor is not None:
        values["actor"] = actor
    return _sql.insert(conn, "task_events", values)


def list_for_task(conn: Conn, task_id: int) -> list[Row]:
    """Events for a task in chronological order (``at`` then ``id``)."""
    query = sql.SQL(
        "SELECT * FROM task_events WHERE task_id = %s ORDER BY at, id"
    )
    return list(conn.execute(query, (task_id,)).fetchall())
