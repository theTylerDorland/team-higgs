"""metrics table.

``report`` executes an operator-authored SQL definition. That definition is
authored by the EM via ``metric define`` — it is trusted input, not external
data — but it is still run inside a READ ONLY transaction (opened by the
command layer) so a mistaken or malformed definition can never mutate state.
"""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError
from emctl.repo import _sql

Row = _sql.Row


def define(
    conn: Conn,
    *,
    name: str,
    definition: str,
    rationale: str,
    status: str | None,
) -> Row:
    values: dict[str, Any] = {
        "name": name,
        "definition": definition,
        "rationale": rationale,
    }
    if status is not None:
        values["status"] = status
    return _sql.insert(conn, "metrics", values)


def get_by_name(conn: Conn, name: str) -> Row:
    row = conn.execute(
        sql.SQL("SELECT * FROM metrics WHERE name = %s"), (name,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"metric '{name}' not found")
    return row


def update(
    conn: Conn,
    *,
    name: str,
    definition: str | None,
    rationale: str | None,
    status: str | None,
) -> Row:
    current = get_by_name(conn, name)
    values: dict[str, Any] = {}
    if definition is not None:
        values["definition"] = definition
    if rationale is not None:
        values["rationale"] = rationale
    if status is not None:
        values["status"] = status
    return _sql.update(conn, "metrics", "metric", int(current["id"]), values)


def list_(conn: Conn, *, status: str | None) -> list[Row]:
    where = {"status": status} if status is not None else None
    return _sql.select(conn, "metrics", where=where)


def report(conn: Conn, *, name: str) -> list[Row]:
    """Run the stored definition and return its rows.

    The connection is opened READ ONLY by the caller. The definition is a
    stored, operator-authored statement executed verbatim; it is not
    concatenated with any external input.
    """
    metric = get_by_name(conn, name)
    definition: str = metric["definition"]
    cursor = conn.execute(definition)  # noqa: S608 - trusted stored SQL, READ ONLY tx
    if cursor.description is None:
        return []
    return list(cursor.fetchall())
