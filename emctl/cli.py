"""Root Typer app.

Mounts each command group and exposes a global ``--json`` that switches every
command to deterministic JSON on stdout. No ``--version`` flag in v1 (reserved
as the BOOTSTRAP phase-2 canary); ``emctl.__version__`` still ships.
"""

from __future__ import annotations

import typer

from emctl import output
from emctl.commands import (
    artifact,
    debt,
    decision,
    learning,
    metric,
    migrate,
    pr,
    project,
    question,
    retro,
    review,
    run,
    status,
    task,
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="emctl — the platform state CLI.",
)


@app.callback()
def main(
    json_: bool = typer.Option(
        False, "--json", help="Emit JSON on stdout instead of a table."
    ),
) -> None:
    output.set_json_mode(json_)


app.add_typer(project.app, name="project")
app.add_typer(task.app, name="task")
app.add_typer(run.app, name="run")
app.add_typer(pr.app, name="pr")
app.add_typer(review.app, name="review")
app.add_typer(artifact.app, name="artifact")
app.add_typer(question.app, name="question")
app.add_typer(decision.app, name="decision")
app.add_typer(metric.app, name="metric")
app.add_typer(learning.app, name="learning")
app.add_typer(debt.app, name="debt")
app.add_typer(retro.app, name="retro")

app.command("status")(status.status_command)
app.command("migrate")(migrate.migrate_command)


if __name__ == "__main__":
    app()
