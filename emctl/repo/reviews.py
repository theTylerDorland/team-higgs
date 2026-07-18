"""reviews table."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn,
    *,
    pr_id: int,
    role: str,
    model: str | None,
    verdict: str,
    findings: Any,
    strongest_objection: str,
) -> Row:
    values: dict[str, Any] = {
        "pr_id": pr_id,
        "role": role,
        "verdict": verdict,
        "strongest_objection": strongest_objection,
        "findings": Jsonb(findings),
    }
    if model is not None:
        values["model"] = model
    return _sql.insert(conn, "reviews", values)
