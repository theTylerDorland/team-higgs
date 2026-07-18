"""pr open|update|show."""

from pathlib import Path

import typer

from emctl import output
from emctl.commands._shared import read_text_file
from emctl.db import transaction
from emctl.enums import PrStatus, RiskLevel
from emctl.repo import prs

app = typer.Typer(no_args_is_help=True, help="Pull requests.")


@app.command("open")
def open_(
    project: int = typer.Option(..., "--project", help="Project id."),
    github_pr: int = typer.Option(..., "--github-pr"),
    risk: RiskLevel | None = typer.Option(None, "--risk"),
    summary_file: Path | None = typer.Option(None, "--summary-file"),
    status: PrStatus | None = typer.Option(None, "--status"),
    task: int | None = typer.Option(None, "--task", help="Task id this PR implements."),
) -> None:
    em_summary = read_text_file(summary_file) if summary_file else None
    with transaction() as conn:
        row = prs.open_(
            conn,
            project_id=project,
            github_pr=github_pr,
            risk_level=risk.value if risk else None,
            em_summary=em_summary,
            status=status.value if status else None,
            task_id=task,
        )
    output.emit_record(row)


@app.command("update")
def update(
    pr_id: int = typer.Argument(..., help="PR id."),
    status: PrStatus | None = typer.Option(None, "--status"),
    risk: RiskLevel | None = typer.Option(None, "--risk"),
    summary_file: Path | None = typer.Option(None, "--summary-file"),
    decision: str | None = typer.Option(None, "--decision"),
    task: int | None = typer.Option(None, "--task", help="Task id this PR implements."),
) -> None:
    em_summary = read_text_file(summary_file) if summary_file else None
    with transaction() as conn:
        row = prs.update(
            conn,
            pr_id,
            status=status.value if status else None,
            risk_level=risk.value if risk else None,
            em_summary=em_summary,
            tyler_decision=decision,
            task_id=task,
        )
    output.emit_record(row)


@app.command("show")
def show(pr_id: int = typer.Argument(..., help="PR id.")) -> None:
    with transaction() as conn:
        row = prs.get(conn, pr_id)
    output.emit_record(row)
