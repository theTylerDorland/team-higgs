"""metric define|update|list|report.

`report` runs the stored definition inside a READ ONLY transaction (see
emctl/repo/metrics.py and docs/stack-backend.md).
"""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import MetricStatus
from emctl.repo import metrics

app = typer.Typer(no_args_is_help=True, help="Metrics.")


@app.command("define")
def define(
    name: str = typer.Option(..., "--name"),
    query: str = typer.Option(..., "--query", help="SQL definition."),
    rationale: str = typer.Option(..., "--rationale"),
    status: MetricStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        row = metrics.define(
            conn,
            name=name,
            definition=query,
            rationale=rationale,
            status=status.value if status else None,
        )
    output.emit_record(row)


@app.command("update")
def update(
    name: str = typer.Option(..., "--name"),
    query: str | None = typer.Option(None, "--query"),
    rationale: str | None = typer.Option(None, "--rationale"),
    status: MetricStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        row = metrics.update(
            conn,
            name=name,
            definition=query,
            rationale=rationale,
            status=status.value if status else None,
        )
    output.emit_record(row)


@app.command("list")
def list_(
    status: MetricStatus | None = typer.Option(None, "--status"),
) -> None:
    with transaction() as conn:
        rows = metrics.list_(conn, status=status.value if status else None)
    output.emit_rows(rows)


@app.command("report")
def report(name: str = typer.Option(..., "--name")) -> None:
    # READ ONLY: a mistaken or malformed definition can only read, never write.
    with transaction(read_only=True) as conn:
        rows = metrics.report(conn, name=name)
    output.emit_rows(rows)
