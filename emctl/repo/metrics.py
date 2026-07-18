"""metrics table.

``report`` executes an operator-authored SQL definition. That definition is
authored by the EM via ``metric define`` — trusted input, not external data —
but the report path treats it as fallible and applies layered controls, in this
order of importance:

1. **READ ONLY transaction — the load-bearing, role-independent control.**
   ``transaction(read_only=True)`` (``emctl/db.py``, opened in
   ``commands/metric.py``) blocks *every* write, including writes performed
   inside PL/pgSQL ``DO`` blocks and VOLATILE / SECURITY DEFINER functions.
   This is the control that actually prevents mutation — do not remove it.
2. **Define-time validation (single ``SELECT``/``WITH``).** ``define``/``update``
   reject anything that is not a single read query, so multi-statement,
   ``DO``-block, and non-read payloads never reach ``metrics.definition`` through
   the CLI in the first place.
3. **Supplementary hardening — not a boundary.** ``SET LOCAL ROLE
   emctl_report_ro`` (migration 0002) plus prepared-statement execution
   (``prepare=True`` → extended protocol, single statement only) stop accidental
   and simple writes and raise the bar. They are **bypassable within a single
   statement**: a ``DO $$ BEGIN RESET ROLE; EXECUTE 'INSERT ...'; END $$`` is one
   top-level statement (so Parse never sees the inner write) and ``RESET ROLE``
   returns to ``session_user`` (Postgres checks SET/RESET ROLE against
   session_user, not the active role), restoring privilege. Only the READ ONLY
   transaction stops that. See docs/stack-backend.md.
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

    The caller MUST open the connection READ ONLY — that is the control that
    actually prevents writes (see module docstring). The role drop and prepared
    execution below are supplementary hardening, not the boundary.
    """
    metric = get_by_name(conn, name)  # read as the app role, before dropping down
    definition: str = metric["definition"]
    # Supplementary hardening (NOT a boundary): SET LOCAL ROLE is bypassable
    # within one statement via PL/pgSQL RESET ROLE; the READ ONLY tx is what
    # holds. See docs/stack-backend.md.
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(REPORT_ROLE)))
    # prepare=True => extended protocol; the server rejects multi-statement input.
    cursor = conn.execute(definition, prepare=True)  # noqa: S608 - trusted, sandboxed
    if cursor.description is None:
        return []
    return list(cursor.fetchall())
