"""project create|show|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import ProjectStatus
from emctl.repo import projects

app = typer.Typer(no_args_is_help=True, help="Projects.")


@app.command("create")
def create(
    name: str = typer.Option(..., "--name"),
    repo: str = typer.Option(..., "--repo"),
    brief: str | None = typer.Option(None, "--brief"),
    status: ProjectStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        row = projects.create(
            conn,
            name=name,
            repo=repo,
            brief=brief,
            status=status.value if status else None,
        )
    output.emit_record(row)


@app.command("show")
def show(ref: str = typer.Argument(..., help="Project id or unique name.")) -> None:
    with transaction() as conn:
        row = projects.get_by_ref(conn, ref)
    output.emit_record(row)


@app.command("list")
def list_(
    status: ProjectStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        rows = projects.list_(conn, status=status.value if status else None)
    output.emit_rows(rows)
