"""The three now-computable metrics (PRD §4) run through the *existing*
`metric report` read-only boundary, and `emctl_report_ro` can read the new
`risks` / `task_events` tables.

The metric SQL below is illustrative test fixture, not registered state: the EM
registers the canonical definitions post-merge (task spec: "Metrics are DATA the
EM registers post-merge — do NOT register metrics"). PRD §4 gives exact SQL only
for `cost_per_merged_pr`; the `cycle_time_days` / `rework_rate` SQL here realises
the PRD's prose and proves the schema supports the queries end to end. Each is a
single SELECT/WITH statement, so it passes define-time validation and runs on the
prepared, SET-LOCAL-ROLE, READ ONLY report path unchanged.
"""

from __future__ import annotations

import pytest

COST_PER_MERGED_PR = (
    "SELECT p.github_pr, coalesce(sum(r.token_cost),0) AS token_cost "
    "FROM prs p JOIN runs r ON r.task_id = p.task_id "
    "WHERE p.status='merged' GROUP BY p.github_pr"
)

CYCLE_TIME_DAYS = (
    "SELECT te.task_id, "
    "EXTRACT(EPOCH FROM ("
    "  max(te.at) FILTER (WHERE te.to_status='done') "
    "- min(te.at) FILTER (WHERE te.to_status='planned'))) / 86400.0 AS cycle_days "
    "FROM task_events te GROUP BY te.task_id "
    "HAVING count(*) FILTER (WHERE te.to_status='done') > 0 "
    "AND count(*) FILTER (WHERE te.to_status='planned') > 0"
)

REWORK_RATE = (
    "WITH events AS ("
    "  SELECT task_id, to_status, "
    "  coalesce(max(CASE WHEN to_status='in_review' THEN 1 ELSE 0 END) OVER ("
    "    PARTITION BY task_id ORDER BY at, id "
    "    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_review "
    "  FROM task_events"
    "), "
    "flags AS ("
    "  SELECT task_id, bool_or("
    "    to_status IN ('in_progress','in_review') AND prior_review = 1"
    "  ) AS reworked "
    "  FROM events GROUP BY task_id"
    ") "
    "SELECT count(*) FILTER (WHERE reworked) AS reworked_tasks, "
    "count(*) AS total_tasks, "
    "round(avg(CASE WHEN reworked THEN 1.0 ELSE 0.0 END), 4) AS rework_rate "
    "FROM flags"
)


@pytest.fixture
def project_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    return int(project["id"])


def test_cost_per_merged_pr_reports(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    invoke(
        "run", "start", "--task", str(task["id"]),
        "--role", "backend", "--model", "m", "--mode", "subagent",
    )
    invoke(
        "run", "finish", "--task", str(task["id"]),
        "--outcome", "done", "--tokens", "100",
    )
    _, pr = invoke(
        "pr", "open", "--project", str(project_id), "--github-pr", "5",
        "--task", str(task["id"]),
    )
    invoke("pr", "update", str(pr["id"]), "--status", "merged")
    invoke(
        "metric", "define", "--name", "cost_per_merged_pr",
        "--query", COST_PER_MERGED_PR, "--rationale", "spend per merged PR",
    )
    result, rows = invoke("metric", "report", "--name", "cost_per_merged_pr")
    assert result.exit_code == 0
    assert rows[0]["github_pr"] == 5
    assert float(rows[0]["token_cost"]) == 100.0


def test_cycle_time_days_reports(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    for status in ("planned", "in_progress", "in_review", "done"):
        invoke("task", "update", str(task["id"]), "--status", status)
    invoke(
        "metric", "define", "--name", "cycle_time_days",
        "--query", CYCLE_TIME_DAYS, "--rationale", "planned -> done latency",
    )
    result, rows = invoke("metric", "report", "--name", "cycle_time_days")
    assert result.exit_code == 0
    assert len(rows) == 1
    assert rows[0]["task_id"] == task["id"]
    assert float(rows[0]["cycle_days"]) >= 0.0


def test_rework_rate_reports(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    # A task that re-enters in_progress after a prior in_review = reworked.
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    for status in ("planned", "in_review", "in_progress"):
        invoke("task", "update", str(task["id"]), "--status", status)
    invoke(
        "metric", "define", "--name", "rework_rate",
        "--query", REWORK_RATE, "--rationale", "share of tasks reworked",
    )
    result, rows = invoke("metric", "report", "--name", "rework_rate")
    assert result.exit_code == 0
    assert rows[0]["reworked_tasks"] == 1
    assert rows[0]["total_tasks"] == 1
    assert float(rows[0]["rework_rate"]) == 1.0


def test_rework_rate_zero_when_no_reentry(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    # A clean forward-only task must not count as reworked.
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    for status in ("planned", "in_progress", "in_review", "done"):
        invoke("task", "update", str(task["id"]), "--status", status)
    invoke(
        "metric", "define", "--name", "rework_rate",
        "--query", REWORK_RATE, "--rationale", "share of tasks reworked",
    )
    _, rows = invoke("metric", "report", "--name", "rework_rate")
    assert rows[0]["reworked_tasks"] == 0
    assert float(rows[0]["rework_rate"]) == 0.0


def test_report_ro_can_select_new_tables(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    """The metric report path SET LOCAL ROLE emctl_report_ro; the role must be
    able to SELECT the v2 tables. If the 0002 default-privilege grant did not
    cover them, this reports an InsufficientPrivilege and fails."""
    invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "security", "--severity", "low",
    )
    invoke("task", "create", "--title", "t", "--project", str(project_id))
    invoke(
        "metric", "define", "--name", "v2_counts",
        "--query",
        "SELECT (SELECT count(*) FROM risks) AS risks, "
        "(SELECT count(*) FROM task_events) AS events",
        "--rationale", "verify report_ro reads v2 tables",
    )
    result, rows = invoke("metric", "report", "--name", "v2_counts")
    assert result.exit_code == 0
    assert rows[0]["risks"] == 1
    assert rows[0]["events"] == 1
