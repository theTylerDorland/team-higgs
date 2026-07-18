"""artifact create|decide|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import ArtifactStatus, ArtifactType
from emctl.repo import artifacts

app = typer.Typer(no_args_is_help=True, help="Artifacts.")


@app.command("create")
def create(
    project: int = typer.Option(..., "--project", help="Project id."),
    type_: ArtifactType = typer.Option(..., "--type"),
    path: str = typer.Option(..., "--path"),
    task: int | None = typer.Option(None, "--task", help="Task id."),
) -> None:
    with transaction() as conn:
        row = artifacts.create(
            conn,
            project_id=project,
            task_id=task,
            type_=type_.value,
            path=path,
        )
    output.emit_record(row)


@app.command("decide")
def decide(
    artifact: int = typer.Option(..., "--artifact", help="Artifact id."),
    status: ArtifactStatus = typer.Option(..., "--status"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    with transaction() as conn:
        row = artifacts.decide(conn, artifact, status=status.value, notes=notes)
    output.emit_record(row)


@app.command("list")
def list_(
    project: int | None = typer.Option(None, "--project"),
    task: int | None = typer.Option(None, "--task"),
    type_: ArtifactType | None = typer.Option(None, "--type"),
) -> None:
    with transaction() as conn:
        rows = artifacts.list_(
            conn,
            project_id=project,
            task_id=task,
            type_=type_.value if type_ else None,
        )
    output.emit_rows(rows)
