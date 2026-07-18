"""decision add|supersede|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import DecisionSignificance, DecisionStatus
from emctl.repo import decisions

app = typer.Typer(no_args_is_help=True, help="Decisions.")


@app.command("add")
def add(
    title: str = typer.Option(..., "--title"),
    decision: str = typer.Option(..., "--decision"),
    project: int | None = typer.Option(None, "--project", help="Project id."),
    context: str | None = typer.Option(None, "--context"),
    significance: DecisionSignificance | None = typer.Option(
        None, "--significance", help="major|minor (default major)."
    ),
    status: DecisionStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        row = decisions.add(
            conn,
            project_id=project,
            title=title,
            context=context,
            decision=decision,
            significance=significance.value if significance else None,
            status=status.value if status else None,
        )
    output.emit_record(row)


@app.command("supersede")
def supersede(
    old_id: int = typer.Argument(..., help="Decision being superseded."),
    by: int = typer.Option(..., "--by", help="Superseding decision id."),
) -> None:
    with transaction() as conn:
        row = decisions.supersede(conn, old_id, new_id=by)
    output.emit_record(row)


@app.command("list")
def list_(
    project: int | None = typer.Option(None, "--project"),
    significance: DecisionSignificance | None = typer.Option(
        None, "--significance"
    ),
    status: DecisionStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        rows = decisions.list_(
            conn,
            project_id=project,
            significance=significance.value if significance else None,
            status=status.value if status else None,
        )
    output.emit_rows(rows)
