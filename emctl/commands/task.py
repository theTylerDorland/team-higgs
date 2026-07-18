"""task create|update|show|list."""

from typing import Any

import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import ModelTier, TaskStatus
from emctl.errors import ValidationError
from emctl.repo import task_events, tasks

app = typer.Typer(no_args_is_help=True, help="Tasks.")


@app.command("create")
def create(
    title: str = typer.Option(..., "--title"),
    project: int = typer.Option(..., "--project", help="Project id."),
    spec: str | None = typer.Option(None, "--spec"),
    role: str | None = typer.Option(None, "--role"),
    tier: ModelTier | None = typer.Option(None, "--tier"),
    prd_ref: str | None = typer.Option(None, "--prd-ref"),
    status: TaskStatus | None = typer.Option(None, "--status"),
    branch: str | None = typer.Option(None, "--branch"),
    depends_on: list[int] = typer.Option([], "--depends-on"),
    by: str | None = typer.Option(None, "--by", help="Acting role."),
) -> None:
    with transaction() as conn:
        row = tasks.create(
            conn,
            project_id=project,
            title=title,
            spec=spec,
            role=role,
            model_tier=tier.value if tier else None,
            prd_ref=prd_ref,
            status=status.value if status else None,
            branch=branch,
            depends_on=list(depends_on) if depends_on else None,
        )
        # Record the opening status as the first history event (from_status
        # NULL on creation). row["status"] reflects the DB default when --status
        # was omitted.
        task_events.add(
            conn,
            task_id=int(row["id"]),
            from_status=None,
            to_status=str(row["status"]),
            actor=by,
        )
    output.emit_record(row)


@app.command("update")
def update(
    task_id: int = typer.Argument(..., help="Task id."),
    status: TaskStatus | None = typer.Option(None, "--status"),
    role: str | None = typer.Option(None, "--role"),
    tier: ModelTier | None = typer.Option(None, "--tier"),
    prd_ref: str | None = typer.Option(None, "--prd-ref"),
    branch: str | None = typer.Option(None, "--branch"),
    depends_on: list[int] = typer.Option([], "--depends-on"),
    blocked_reason: str | None = typer.Option(None, "--blocked-reason"),
    unblock: bool = typer.Option(False, "--unblock"),
    by: str | None = typer.Option(None, "--by", help="Acting role."),
) -> None:
    if blocked_reason is not None and unblock:
        raise ValidationError("--blocked-reason and --unblock are mutually exclusive")
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status.value
    if role is not None:
        values["role"] = role
    if tier is not None:
        values["model_tier"] = tier.value
    if prd_ref is not None:
        values["prd_ref"] = prd_ref
    if branch is not None:
        values["branch"] = branch
    if depends_on:
        values["depends_on"] = list(depends_on)
    if blocked_reason is not None:
        values["blocked"] = True
        values["blocked_reason"] = blocked_reason
    if unblock:
        values["blocked"] = False
        values["blocked_reason"] = None
    with transaction() as conn:
        # Read the prior status first so a genuine status change writes a
        # task_events row with the correct from/to (PRD §4). Also surfaces a
        # clean not-found before any write.
        current = tasks.get(conn, task_id)
        row = tasks.update(conn, task_id, values)
        if status is not None and status.value != current["status"]:
            task_events.add(
                conn,
                task_id=task_id,
                from_status=str(current["status"]),
                to_status=status.value,
                actor=by,
            )
    output.emit_record(row)


@app.command("history")
def history(task_id: int = typer.Argument(..., help="Task id.")) -> None:
    with transaction() as conn:
        tasks.get(conn, task_id)  # not-found -> exit 3 before listing
        rows = task_events.list_for_task(conn, task_id)
    output.emit_rows(rows)


@app.command("show")
def show(task_id: int = typer.Argument(..., help="Task id.")) -> None:
    with transaction() as conn:
        row = tasks.get(conn, task_id)
    output.emit_record(row)


@app.command("list")
def list_(
    status: TaskStatus | None = typer.Option(None, "--status"),
    project: int | None = typer.Option(None, "--project"),
    role: str | None = typer.Option(None, "--role"),
    blocked: bool | None = typer.Option(None, "--blocked"),
) -> None:
    with transaction() as conn:
        rows = tasks.list_(
            conn,
            status=status.value if status else None,
            project_id=project,
            role=role,
            blocked=blocked,
        )
    output.emit_rows(rows)
