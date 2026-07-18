"""risks table (EM-curated risk register)."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    project_id: int,
    title: str,
    body: str | None,
    category: str,
    severity: str,
    status: str | None,
    mitigation: str | None,
    decision_id: int | None,
    pr_id: int | None,
    acknowledged_by: str | None,
) -> Row:
    values: dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "category": category,
        "severity": severity,
    }
    optional = {
        "body": body,
        "status": status,
        "mitigation": mitigation,
        "decision_id": decision_id,
        "pr_id": pr_id,
        "acknowledged_by": acknowledged_by,
    }
    for key, value in optional.items():
        if value is not None:
            values[key] = value
    # A risk that opens already dispositioned (status off 'acknowledged') gets
    # resolved_at set at creation, mirroring `update` below.
    extra: list[Any] = []
    if status is not None and status != "acknowledged":
        extra.append(sql.SQL("resolved_at = now()"))
    if not extra:
        return _sql.insert(conn, "risks", values)
    columns = list(values)
    query = sql.SQL(
        "INSERT INTO risks ({cols}, resolved_at) VALUES ({vals}, now()) "
        "RETURNING *"
    ).format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    row = conn.execute(query, list(values.values())).fetchone()
    assert row is not None
    return row


def get(conn: Conn, risk_id: int) -> Row:
    return _sql.get(conn, "risks", "risk", risk_id)


def update(
    conn: Conn,
    risk_id: int,
    *,
    status: str | None,
    severity: str | None,
    mitigation: str | None,
    decision_id: int | None,
) -> Row:
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status
    if severity is not None:
        values["severity"] = severity
    if mitigation is not None:
        values["mitigation"] = mitigation
    if decision_id is not None:
        values["decision_id"] = decision_id
    # Leaving 'acknowledged' resolves the risk (PRD §3): stamp resolved_at.
    # Reopening (back to 'acknowledged') clears it so the register's own data
    # stays consistent.
    extra: list[Any] = []
    if status is not None:
        if status != "acknowledged":
            extra.append(sql.SQL("resolved_at = now()"))
        else:
            extra.append(sql.SQL("resolved_at = NULL"))
    return _sql.update(
        conn, "risks", "risk", risk_id, values, extra=extra or None
    )


def list_(
    conn: Conn,
    *,
    project_id: int | None,
    status: str | None,
    category: str | None,
    severity: str | None,
) -> list[Row]:
    where: dict[str, Any] = {}
    if project_id is not None:
        where["project_id"] = project_id
    if status is not None:
        where["status"] = status
    if category is not None:
        where["category"] = category
    if severity is not None:
        where["severity"] = severity
    return _sql.select(conn, "risks", where=where or None)


def show(conn: Conn, risk_id: int) -> Row:
    """Full risk row plus the linked decision/PR rows (or None)."""
    risk = get(conn, risk_id)
    linked_decision: Row | None = None
    if risk.get("decision_id") is not None:
        linked_decision = conn.execute(
            sql.SQL("SELECT * FROM decisions WHERE id = %s"),
            (risk["decision_id"],),
        ).fetchone()
    linked_pr: Row | None = None
    if risk.get("pr_id") is not None:
        linked_pr = conn.execute(
            sql.SQL("SELECT * FROM prs WHERE id = %s"), (risk["pr_id"],)
        ).fetchone()
    return {**risk, "linked_decision": linked_decision, "linked_pr": linked_pr}
