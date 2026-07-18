"""risk add|update|list|show — the EM-curated risk register (PRD §4)."""

import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import RiskCategory, RiskStatus, Severity
from emctl.repo import risks

app = typer.Typer(no_args_is_help=True, help="Risk register.")


@app.command("add")
def add(
    project: int = typer.Option(..., "--project", help="Project id."),
    title: str = typer.Option(..., "--title"),
    category: RiskCategory = typer.Option(..., "--category"),
    severity: Severity = typer.Option(..., "--severity"),
    body: str | None = typer.Option(None, "--body"),
    status: RiskStatus | None = typer.Option(None, "--status"),
    mitigation: str | None = typer.Option(None, "--mitigation"),
    decision: int | None = typer.Option(None, "--decision", help="Decision id."),
    pr: int | None = typer.Option(None, "--pr", help="PR id."),
    by: str | None = typer.Option(None, "--by", help="Acknowledging role."),
) -> None:
    with transaction() as conn:
        row = risks.add(
            conn,
            project_id=project,
            title=title,
            body=body,
            category=category.value,
            severity=severity.value,
            status=status.value if status else None,
            mitigation=mitigation,
            decision_id=decision,
            pr_id=pr,
            acknowledged_by=by,
        )
    output.emit_record(row)


@app.command("update")
def update(
    risk_id: int = typer.Argument(..., help="Risk id."),
    status: RiskStatus | None = typer.Option(None, "--status"),
    severity: Severity | None = typer.Option(None, "--severity"),
    mitigation: str | None = typer.Option(None, "--mitigation"),
    decision: int | None = typer.Option(None, "--decision", help="Decision id."),
) -> None:
    with transaction() as conn:
        row = risks.update(
            conn,
            risk_id,
            status=status.value if status else None,
            severity=severity.value if severity else None,
            mitigation=mitigation,
            decision_id=decision,
        )
    output.emit_record(row)


@app.command("list")
def list_(
    project: int | None = typer.Option(None, "--project"),
    status: RiskStatus | None = typer.Option(None, "--status"),
    category: RiskCategory | None = typer.Option(None, "--category"),
    severity: Severity | None = typer.Option(None, "--severity"),
) -> None:
    with transaction() as conn:
        rows = risks.list_(
            conn,
            project_id=project,
            status=status.value if status else None,
            category=category.value if category else None,
            severity=severity.value if severity else None,
        )
    output.emit_rows(rows)


@app.command("show")
def show(risk_id: int = typer.Argument(..., help="Risk id.")) -> None:
    with transaction() as conn:
        row = risks.show(conn, risk_id)
    output.emit_record(row)
