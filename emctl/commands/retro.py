"""retro open|close|list."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.repo import retros

app = typer.Typer(no_args_is_help=True, help="Retros.")


@app.command("open")
def open_(
    trigger: str = typer.Option(..., "--trigger"),
    doc_path: str | None = typer.Option(None, "--doc-path"),
) -> None:
    with transaction() as conn:
        row = retros.open_(conn, trigger=trigger, doc_path=doc_path)
    output.emit_record(row)


@app.command("close")
def close(
    retro: int = typer.Option(..., "--retro", help="Retro id."),
) -> None:
    with transaction() as conn:
        row = retros.close(conn, retro)
    output.emit_record(row)


@app.command("list")
def list_() -> None:
    with transaction() as conn:
        rows = retros.list_(conn)
    output.emit_rows(rows)
