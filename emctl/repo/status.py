"""Cross-table summary for `emctl status`. Read-only.

Every query here is a fixed literal with no parameters — no external input is
interpolated.
"""

from __future__ import annotations

from typing import Any

from emctl.db import Conn

Section = list[dict[str, Any]]


def summary(conn: Conn) -> dict[str, Any]:
    active_projects = conn.execute(
        "SELECT id, name, repo, status FROM projects "
        "WHERE status = 'active' ORDER BY id"
    ).fetchall()
    task_counts = conn.execute(
        "SELECT status, count(*) AS count FROM tasks "
        "GROUP BY status ORDER BY status"
    ).fetchall()
    awaiting_tyler = conn.execute(
        "SELECT id, title, project_id FROM tasks "
        "WHERE status = 'awaiting_tyler' ORDER BY id"
    ).fetchall()
    open_questions = conn.execute(
        "SELECT id, project_id, blocking, body FROM questions "
        "WHERE answer IS NULL ORDER BY blocking DESC, id"
    ).fetchall()
    open_prs = conn.execute(
        "SELECT id, project_id, github_pr, status, risk_level FROM prs "
        "WHERE status = 'open' ORDER BY id"
    ).fetchall()
    recent_run_costs = conn.execute(
        "SELECT id, task_id, role, outcome, token_cost FROM runs "
        "ORDER BY started_at DESC, id DESC LIMIT 10"
    ).fetchall()
    return {
        "active_projects": list(active_projects),
        "task_counts": list(task_counts),
        "awaiting_tyler": list(awaiting_tyler),
        "open_questions": list(open_questions),
        "open_prs": list(open_prs),
        "recent_run_costs": list(recent_run_costs),
    }
