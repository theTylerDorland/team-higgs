"""run start|finish|update."""

from decimal import Decimal

import typer

from emctl import output
from emctl.db import transaction
from emctl.enums import RunMode, RunOutcome
from emctl.errors import ValidationError
from emctl.repo import runs

app = typer.Typer(no_args_is_help=True, help="Runs.")


def _parse_cost(cost: str | None) -> Decimal | None:
    if cost is None:
        return None
    try:
        return Decimal(cost)
    except (ArithmeticError, ValueError) as exc:
        raise ValidationError(f"--cost is not a number: {cost}") from exc


def _token_flags(
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read: int | None,
    cache_write: int | None,
) -> dict[str, int | None]:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
    }


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
    input_tokens: int | None = typer.Option(None, "--input-tokens"),
    output_tokens: int | None = typer.Option(None, "--output-tokens"),
    cache_read: int | None = typer.Option(None, "--cache-read"),
    cache_write: int | None = typer.Option(None, "--cache-write"),
) -> None:
    if run is None and task is None:
        raise ValidationError("run finish requires --run or --task")
    cost_usd = _parse_cost(cost)
    with transaction() as conn:
        row = runs.finish(
            conn,
            run_id=run,
            task_id=task,
            outcome=outcome.value,
            token_cost=tokens,
            cost_usd=cost_usd,
            log_ref=log_ref,
            tokens=_token_flags(
                input_tokens, output_tokens, cache_read, cache_write
            ),
        )
    output.emit_record(row)


@app.command("update")
def update(
    run_id: int = typer.Argument(..., help="Run id."),
    outcome: RunOutcome | None = typer.Option(None, "--outcome"),
    tokens: int | None = typer.Option(None, "--tokens"),
    cost: str | None = typer.Option(None, "--cost", help="USD, e.g. 1.2500"),
    log_ref: str | None = typer.Option(None, "--log-ref"),
    input_tokens: int | None = typer.Option(None, "--input-tokens"),
    output_tokens: int | None = typer.Option(None, "--output-tokens"),
    cache_read: int | None = typer.Option(None, "--cache-read"),
    cache_write: int | None = typer.Option(None, "--cache-write"),
) -> None:
    """Amend an already-finished run (correction / historical backfill).

    Unknown RUN_ID -> NotFoundError (exit 3); a bad enum/value is rejected by
    Typer / cost parsing (exit 2). ``ended_at`` is left untouched.
    """
    cost_usd = _parse_cost(cost)
    with transaction() as conn:
        row = runs.update(
            conn,
            run_id=run_id,
            outcome=outcome.value if outcome else None,
            token_cost=tokens,
            cost_usd=cost_usd,
            log_ref=log_ref,
            tokens=_token_flags(
                input_tokens, output_tokens, cache_read, cache_write
            ),
        )
    output.emit_record(row)
