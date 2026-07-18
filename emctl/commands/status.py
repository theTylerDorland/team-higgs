"""status — global read-only summary."""

from emctl import output
from emctl.db import transaction
from emctl.repo import status as status_repo


def status_command() -> None:
    """Active projects, task counts, awaiting-Tyler queue, open questions,
    open PRs, and recent run token costs."""
    with transaction(read_only=True) as conn:
        summary = status_repo.summary(conn)
    output.emit_status(summary)
