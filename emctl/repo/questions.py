"""questions table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn, *, project_id: int | None, body: str, blocking: bool
) -> Row:
    values: dict[str, Any] = {"body": body, "blocking": blocking}
    if project_id is not None:
        values["project_id"] = project_id
    return _sql.insert(conn, "questions", values)


def answer(conn: Conn, question_id: int, *, answer: str) -> Row:
    extra = [sql.SQL("answered_at = now()")]
    return _sql.update(
        conn, "questions", "question", question_id, {"answer": answer}, extra=extra
    )


def list_(conn: Conn, *, blocking_only: bool) -> list[Row]:
    if blocking_only:
        query = sql.SQL(
            "SELECT * FROM questions WHERE blocking = true AND answer IS NULL "
            "ORDER BY id"
        )
        return list(conn.execute(query).fetchall())
    return _sql.select(conn, "questions")
