"""Rendering. Human tables by default; ``--json`` switches every command to
deterministic JSON on stdout and nothing else.

Timestamps are emitted as ISO-8601 in UTC. JSON is sorted by key so agents get
stable output. Error text is never rendered here — it travels on stderr via
:mod:`emctl.errors`.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import typer

_json_mode = False


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def json_mode() -> bool:
    return _json_mode


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=_json_default, sort_keys=True)
    return str(value)


def _dumps(data: Any) -> str:
    return json.dumps(data, default=_json_default, sort_keys=True)


def _render_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        typer.echo("(no rows)")
        return
    columns = list(rows[0].keys())
    widths = {c: len(c) for c in columns}
    cells = []
    for row in rows:
        rendered = {c: _cell(row.get(c)) for c in columns}
        for c in columns:
            widths[c] = max(widths[c], len(rendered[c]))
        cells.append(rendered)
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    typer.echo(header)
    typer.echo("  ".join("-" * widths[c] for c in columns))
    for rendered in cells:
        typer.echo("  ".join(rendered[c].ljust(widths[c]) for c in columns))


def _render_record(row: dict[str, Any]) -> None:
    if not row:
        typer.echo("(empty)")
        return
    width = max(len(k) for k in row)
    for key, value in row.items():
        typer.echo(f"{key.ljust(width)}  {_cell(value)}")


def emit_record(row: dict[str, Any]) -> None:
    """Emit a single record (create/update/show/finish results)."""
    if _json_mode:
        typer.echo(_dumps(row))
    else:
        _render_record(row)


def emit_rows(rows: list[dict[str, Any]]) -> None:
    """Emit a list of records (``list`` commands)."""
    if _json_mode:
        typer.echo(_dumps(rows))
    else:
        _render_table(rows)


def emit_status(summary: dict[str, Any]) -> None:
    """Emit the cross-table ``status`` summary."""
    if _json_mode:
        typer.echo(_dumps(summary))
        return
    for section, value in summary.items():
        typer.echo(f"== {section} ==")
        if isinstance(value, list):
            _render_table(value)
        elif isinstance(value, dict):
            _render_record(value)
        else:
            typer.echo(_cell(value))
        typer.echo("")
