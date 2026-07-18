"""learning add|list|resolve."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import LearningCategory, LearningStatus
from emctl.repo import learnings

app = typer.Typer(no_args_is_help=True, help="Learnings.")


@app.command("add")
def add(
    category: LearningCategory = typer.Option(..., "--category"),
    observation: str = typer.Option(..., "--observation"),
    evidence: str | None = typer.Option(None, "--evidence"),
    role: str | None = typer.Option(None, "--role", help="Sets filed_by."),
) -> None:
    with transaction() as conn:
        row = learnings.add(
            conn,
            category=category.value,
            observation=observation,
            evidence=evidence,
            filed_by=role,
        )
    output.emit_record(row)


@app.command("resolve")
def resolve(
    learning: int = typer.Option(..., "--learning", help="Learning id."),
    retro: int = typer.Option(..., "--retro", help="Retro id."),
) -> None:
    with transaction() as conn:
        row = learnings.resolve(conn, learning, retro_id=retro)
    output.emit_record(row)


@app.command("list")
def list_(
    category: LearningCategory | None = typer.Option(None, "--category"),
    status: LearningStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        rows = learnings.list_(
            conn,
            category=category.value if category else None,
            status=status.value if status else None,
        )
    output.emit_rows(rows)
