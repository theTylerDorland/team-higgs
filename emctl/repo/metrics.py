"""metrics table.

``report`` executes an operator-authored SQL definition. That definition is
authored by the EM via ``metric define`` — trusted input, not external data —
but the report path treats it as fallible and applies layered controls so it
can only ever read:

1. **Least-privilege role (primary boundary).** ``SET LOCAL ROLE
   emctl_report_ro`` (provisioned by migration 0002) drops all write privilege
   before the definition runs; a write/DDL attempt fails with
   insufficient_privilege.
2. **Single statement.** The definition is executed as a prepared statement
   (``prepare=True`` → the extended query protocol), whose Parse phase rejects
   ``;``-separated multi-statement input. This is essential, not cosmetic: a
   ``COMMIT`` inside a multi-statement definition would end the transaction and
   discard ``SET LOCAL ROLE``, so blocking multi-statement is what keeps the
   role boundary intact against the ``COMMIT; BEGIN READ WRITE; ...`` escape.
3. **READ ONLY transaction.** Opened by the command layer as a second guard.
4. **Define-time validation.** ``define``/``update`` reject a definition that
   is not a single ``SELECT``/``WITH`` statement — fast-fail UX, not the
   boundary.
"""

from __future__ import annotations

import re
from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError, ValidationError
from emctl.repo import _sql

Row = _sql.Row

REPORT_ROLE = "emctl_report_ro"

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")


def _strip_comments(text: str) -> str:
    return _LINE_COMMENT.sub(" ", _BLOCK_COMMENT.sub(" ", text))


def validate_definition(definition: str) -> None:
    """Fast-fail check that a definition is a single read query.

    This is UX, not the security boundary (the role is). It rejects the obvious
    footguns early with a clear message: multiple statements, or a leading
    keyword other than SELECT/WITH.
    """
    body = _strip_comments(definition).strip().rstrip(";").rstrip()
    if not body:
        raise ValidationError("metric definition is empty")
    if ";" in body:
        raise ValidationError("metric definition must be a single statement")
    first = body.split(None, 1)[0].lower()
    if first not in ("select", "with"):
        raise ValidationError(
            "metric definition must be a single SELECT or WITH query"
        )


def define(
    conn: Conn,
    *,
    name: str,
    definition: str,
    rationale: str,
    status: str | None,
) -> Row:
    validate_definition(definition)
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
    if definition is not None:
        validate_definition(definition)
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

    The caller opens the connection READ ONLY. Here we additionally drop to the
    least-privilege ``emctl_report_ro`` role and run the definition as a
    prepared statement so only a single, write-less statement can execute.
    """
    metric = get_by_name(conn, name)  # read as the app role, before dropping down
    definition: str = metric["definition"]
    # Primary boundary: no write privilege for the definition's execution.
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(REPORT_ROLE)))
    # prepare=True => extended protocol; the server rejects multi-statement input.
    cursor = conn.execute(definition, prepare=True)  # noqa: S608 - trusted, sandboxed
    if cursor.description is None:
        return []
    return list(cursor.fetchall())
