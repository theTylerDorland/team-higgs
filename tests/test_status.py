"""status aggregates across tables."""

from __future__ import annotations


def test_status_aggregates_seeded_data(invoke) -> None:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    pid = str(project["id"])
    _, task = invoke("task", "create", "--title", "t", "--project", pid)
    invoke("task", "update", str(task["id"]), "--status", "awaiting_tyler")
    invoke("pr", "open", "--project", pid, "--github-pr", "3")
    invoke("question", "add", "--body", "blocking q?", "--blocking")
    invoke("question", "add", "--body", "non-blocking q?")

    _, summary = invoke("status")

    assert [p["name"] for p in summary["active_projects"]] == ["p"]
    counts = {row["status"]: row["count"] for row in summary["task_counts"]}
    assert counts == {"awaiting_tyler": 1}
    assert [t["id"] for t in summary["awaiting_tyler"]] == [task["id"]]
    assert [pr["github_pr"] for pr in summary["open_prs"]] == [3]
    # Blocking question sorts first.
    assert summary["open_questions"][0]["blocking"] is True
    assert len(summary["open_questions"]) == 2


def test_status_table_mode_renders(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("status", json_mode=False)
    assert result.exit_code == 0
    assert "active_projects" in result.output
