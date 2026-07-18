"""run start|finish."""

from decimal import Decimal

import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import RunMode, RunOutcome
from emctl.errors import ValidationError
from emctl.repo import runs

app = typer.Typer(no_args_is_help=True, help="Runs.")


@app.command("start")
def start(
    task: int | None = typer.Option(None, "--task", help="Task id."),
    role: str = typer.Option(..., "--role"),
    model: str = typer.Option(..., "--model"),
    mode: RunMode = typer.Option(..., "--mode"),
) -> None:
    with transaction() as conn:
        row = runs.start(
            conn, task_id=task, role=role, model=model, mode=mode.value
        )
    output.emit_record(row)


@app.command("finish")
def finish(
    run: int | None = typer.Option(None, "--run", help="Run id."),
    task: int | None = typer.Option(
        None, "--task", help="Finish this task's latest open run."
    ),
    outcome: RunOutcome = typer.Option(..., "--outcome"),
    tokens: int | None = typer.Option(None, "--tokens"),
    cost: str | None = typer.Option(None, "--cost", help="USD, e.g. 1.2500"),
    log_ref: str | None = typer.Option(None, "--log-ref"),
) -> None:
    if run is None and task is None:
        raise ValidationError("run finish requires --run or --task")
    cost_usd: Decimal | None = None
    if cost is not None:
        try:
            cost_usd = Decimal(cost)
        except (ArithmeticError, ValueError) as exc:
            raise ValidationError(f"--cost is not a number: {cost}") from exc
    with transaction() as conn:
        row = runs.finish(
            conn,
            run_id=run,
            task_id=task,
            outcome=outcome.value,
            token_cost=tokens,
            cost_usd=cost_usd,
            log_ref=log_ref,
        )
    output.emit_record(row)
