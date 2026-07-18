"""decision add|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.repo import decisions

app = typer.Typer(no_args_is_help=True, help="Decisions.")


@app.command("add")
def add(
    title: str = typer.Option(..., "--title"),
    decision: str = typer.Option(..., "--decision"),
    project: int | None = typer.Option(None, "--project", help="Project id."),
    context: str | None = typer.Option(None, "--context"),
) -> None:
    with transaction() as conn:
        row = decisions.add(
            conn,
            project_id=project,
            title=title,
            context=context,
            decision=decision,
        )
    output.emit_record(row)


@app.command("list")
def list_(
    project: int | None = typer.Option(None, "--project"),
) -> None:
    with transaction() as conn:
        rows = decisions.list_(conn, project_id=project)
    output.emit_rows(rows)
