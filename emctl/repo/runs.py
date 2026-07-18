"""runs table."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError
from emctl.repo import _sql

Row = _sql.Row

# The four typed token columns (migration 0004). Order is display-only.
TOKEN_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def _token_values(tokens: dict[str, int | None]) -> dict[str, Any]:
    """Keep only the token columns that were actually supplied (not None), so
    an omitted flag never overwrites a stored value with NULL."""
    return {col: tokens[col] for col in TOKEN_COLUMNS if tokens.get(col) is not None}


def start(
    conn: Conn, *, task_id: int | None, role: str, model: str, mode: str
) -> Row:
    values: dict[str, Any] = {"role": role, "model": model, "mode": mode}
    if task_id is not None:
        values["task_id"] = task_id
    return _sql.insert(conn, "runs", values)


def _latest_open_run_id(conn: Conn, task_id: int) -> int:
    query = sql.SQL(
        "SELECT id FROM runs WHERE task_id = %s AND ended_at IS NULL "
        "ORDER BY started_at DESC, id DESC LIMIT 1"
    )
    row = conn.execute(query, (task_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"no open run for task {task_id}")
    return int(row["id"])


def finish(
    conn: Conn,
    *,
    run_id: int | None,
    task_id: int | None,
    outcome: str,
    token_cost: int | None,
    cost_usd: Decimal | None,
    log_ref: str | None,
    tokens: dict[str, int | None] | None = None,
) -> Row:
    if run_id is None:
        if task_id is None:
            # Guarded by the command layer; kept for defence in depth.
            raise NotFoundError("run finish requires --run or --task")
        run_id = _latest_open_run_id(conn, task_id)
    values: dict[str, Any] = {"outcome": outcome}
    if token_cost is not None:
        values["token_cost"] = token_cost
    if cost_usd is not None:
        values["cost_usd"] = cost_usd
    if log_ref is not None:
        values["log_ref"] = log_ref
    if tokens is not None:
        values.update(_token_values(tokens))
    extra = [sql.SQL("ended_at = now()")]
    return _sql.update(conn, "runs", "run", run_id, values, extra=extra)


def update(
    conn: Conn,
    *,
    run_id: int,
    outcome: str | None,
    token_cost: int | None,
    cost_usd: Decimal | None,
    log_ref: str | None,
    tokens: dict[str, int | None] | None = None,
) -> Row:
    """Amend an already-finished run (correction / historical backfill).

    Only supplied fields are written; ``ended_at`` is left as-is (this is not a
    finish). An unknown ``run_id`` surfaces as NotFoundError via ``_sql.update``
    (or ``_sql.get`` when no fields were supplied)."""
    values: dict[str, Any] = {}
    if outcome is not None:
        values["outcome"] = outcome
    if token_cost is not None:
        values["token_cost"] = token_cost
    if cost_usd is not None:
        values["cost_usd"] = cost_usd
    if log_ref is not None:
        values["log_ref"] = log_ref
    if tokens is not None:
        values.update(_token_values(tokens))
    return _sql.update(conn, "runs", "run", run_id, values)
