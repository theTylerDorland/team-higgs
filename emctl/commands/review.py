"""review add."""

from pathlib import Path

import typer

from emctl import output
from emctl.commands._shared import read_json_file
from emctl.db import transaction
from emctl.enums import Verdict
from emctl.repo import reviews

app = typer.Typer(no_args_is_help=True, help="Reviews.")


@app.command("add")
def add(
    pr: int = typer.Option(..., "--pr", help="PR id."),
    role: str = typer.Option(..., "--role"),
    verdict: Verdict = typer.Option(..., "--verdict"),
    objection: str = typer.Option(..., "--objection", help="Strongest objection."),
    model: str | None = typer.Option(None, "--model"),
    findings_file: Path | None = typer.Option(None, "--findings-file"),
) -> None:
    findings = read_json_file(findings_file) if findings_file else []
    with transaction() as conn:
        row = reviews.add(
            conn,
            pr_id=pr,
            role=role,
            model=model,
            verdict=verdict.value,
            findings=findings,
            strongest_objection=objection,
        )
    output.emit_record(row)
