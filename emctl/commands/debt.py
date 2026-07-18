"""debt add|list|resolve|merge."""


import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import DebtKind, DebtStatus, Severity
from emctl.repo import debt

app = typer.Typer(no_args_is_help=True, help="Technical debt.")


@app.command("add")
def add(
    where: str = typer.Option(..., "--where", help="Location; required."),
    kind: DebtKind = typer.Option(..., "--kind"),
    severity: Severity = typer.Option(..., "--severity"),
    evidence: str = typer.Option(..., "--evidence"),
    project: int | None = typer.Option(None, "--project", help="Project id."),
    role: str | None = typer.Option(None, "--role", help="Sets filed_by."),
) -> None:
    with transaction() as conn:
        row = debt.add(
            conn,
            project_id=project,
            location=where,
            kind=kind.value,
            severity=severity.value,
            evidence=evidence,
            filed_by=role,
        )
    output.emit_record(row)


@app.command("resolve")
def resolve(
    debt_id: int = typer.Option(..., "--debt", help="Debt id."),
    resolved_ref: str = typer.Option(..., "--resolved-ref"),
) -> None:
    with transaction() as conn:
        row = debt.resolve(conn, debt_id, resolved_ref=resolved_ref)
    output.emit_record(row)


@app.command("merge")
def merge(
    into: int = typer.Option(..., "--into", help="Keeper debt id."),
    dups: list[int] = typer.Argument(..., help="Duplicate debt ids."),
) -> None:
    with transaction() as conn:
        row = debt.merge(conn, keeper_id=into, dup_ids=list(dups))
    output.emit_record(row)


@app.command("list")
def list_(
    status: DebtStatus | None = typer.Option(None, "--status"),
    severity: Severity | None = typer.Option(None, "--severity"),
    kind: DebtKind | None = typer.Option(None, "--kind"),
) -> None:
    with transaction() as conn:
        rows = debt.list_(
            conn,
            status=status.value if status else None,
            severity=severity.value if severity else None,
            kind=kind.value if kind else None,
        )
    output.emit_rows(rows)
