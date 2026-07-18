"""task_events: create/update write history; `task history` reads it (PRD §4)."""

from __future__ import annotations

import pytest


@pytest.fixture
def project_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    return int(project["id"])


def test_create_writes_opening_event(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke(
        "task", "create", "--title", "t", "--project", str(project_id), "--by", "em"
    )
    _, events = invoke("task", "history", str(task["id"]))
    assert len(events) == 1
    assert events[0]["from_status"] is None
    assert events[0]["to_status"] == "backlog"  # DB default status
    assert events[0]["actor"] == "em"


def test_create_with_explicit_status_records_it(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke(
        "task", "create", "--title", "t", "--project", str(project_id),
        "--status", "planned",
    )
    _, events = invoke("task", "history", str(task["id"]))
    assert events[0]["to_status"] == "planned"
    assert events[0]["from_status"] is None
    assert events[0]["actor"] is None


def test_status_change_writes_event_with_from_to_actor(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    invoke(
        "task", "update", str(task["id"]), "--status", "in_review", "--by", "backend"
    )
    _, events = invoke("task", "history", str(task["id"]))
    assert len(events) == 2  # opening + the change
    change = events[-1]
    assert change["from_status"] == "backlog"
    assert change["to_status"] == "in_review"
    assert change["actor"] == "backend"


def test_no_status_change_writes_no_event(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    # An update that doesn't touch status must not append history.
    invoke("task", "update", str(task["id"]), "--role", "backend")
    _, events = invoke("task", "history", str(task["id"]))
    assert len(events) == 1


def test_status_update_to_same_value_writes_no_event(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke(
        "task", "create", "--title", "t", "--project", str(project_id),
        "--status", "planned",
    )
    invoke("task", "update", str(task["id"]), "--status", "planned")
    _, events = invoke("task", "history", str(task["id"]))
    assert len(events) == 1  # no-op status change adds nothing


def test_history_is_chronological(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    for status in ("planned", "in_progress", "in_review", "done"):
        invoke("task", "update", str(task["id"]), "--status", status)
    _, events = invoke("task", "history", str(task["id"]))
    assert [e["to_status"] for e in events] == [
        "backlog", "planned", "in_progress", "in_review", "done"
    ]


def test_history_unknown_task_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("task", "history", "9999")
    assert result.exit_code == 3
