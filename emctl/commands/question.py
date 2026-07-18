"""question add|answer|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.repo import questions

app = typer.Typer(no_args_is_help=True, help="Questions.")


@app.command("add")
def add(
    body: str = typer.Option(..., "--body"),
    project: int | None = typer.Option(None, "--project", help="Project id."),
    blocking: bool = typer.Option(False, "--blocking"),
) -> None:
    with transaction() as conn:
        row = questions.add(
            conn, project_id=project, body=body, blocking=blocking
        )
    output.emit_record(row)


@app.command("answer")
def answer(
    question: int = typer.Option(..., "--question", help="Question id."),
    answer: str = typer.Option(..., "--answer"),
) -> None:
    with transaction() as conn:
        row = questions.answer(conn, question, answer=answer)
    output.emit_record(row)


@app.command("list")
def list_(
    blocking: bool = typer.Option(
        False, "--blocking", help="Only open blocking questions."
    ),
) -> None:
    with transaction() as conn:
        rows = questions.list_(conn, blocking_only=blocking)
    output.emit_rows(rows)
