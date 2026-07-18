"""debt table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import ValidationError
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    project_id: int | None,
    location: str,
    kind: str,
    severity: str,
    evidence: str,
    filed_by: str | None,
) -> Row:
    values: dict[str, Any] = {
        "location": location,
        "kind": kind,
        "severity": severity,
        "evidence": evidence,
    }
    if project_id is not None:
        values["project_id"] = project_id
    if filed_by is not None:
        values["filed_by"] = filed_by
    return _sql.insert(conn, "debt", values)


def resolve(conn: Conn, debt_id: int, *, resolved_ref: str) -> Row:
    return _sql.update(
        conn,
        "debt",
        "debt item",
        debt_id,
        {"status": "resolved", "resolved_ref": resolved_ref},
    )


def merge(conn: Conn, *, keeper_id: int, dup_ids: list[int]) -> Row:
    """Resolve each duplicate with a pointer to the keeper and bump the
    keeper's recurrence by the number of duplicates merged in."""
    if not dup_ids:
        raise ValidationError("merge needs at least one duplicate id")
    # Confirm the keeper exists before touching duplicates (raises NotFound).
    _sql.get(conn, "debt", "debt item", keeper_id)
    pointer = f"merged into #{keeper_id}"
    for dup_id in dup_ids:
        if dup_id == keeper_id:
            raise ValidationError("cannot merge a debt item into itself")
        _sql.update(
            conn,
            "debt",
            "debt item",
            dup_id,
            {"status": "resolved", "resolved_ref": pointer},
        )
    query = sql.SQL(
        "UPDATE debt SET recurrence = recurrence + %s WHERE id = %s RETURNING *"
    )
    row = conn.execute(query, (len(dup_ids), keeper_id)).fetchone()
    assert row is not None  # keeper existence already confirmed above
    return row


def list_(
    conn: Conn, *, status: str | None, severity: str | None, kind: str | None
) -> list[Row]:
    where: dict[str, Any] = {}
    if status is not None:
        where["status"] = status
    if severity is not None:
        where["severity"] = severity
    if kind is not None:
        where["kind"] = kind
    return _sql.select(conn, "debt", where=where or None)
