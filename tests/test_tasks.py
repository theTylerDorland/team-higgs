"""task create/update/list, depends_on array, block toggles, bad enum."""

from __future__ import annotations

import pytest


@pytest.fixture
def project_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    return int(project["id"])


def test_depends_on_array_round_trips(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke(
        "task",
        "create",
        "--title",
        "t",
        "--project",
        str(project_id),
        "--depends-on",
        "1",
        "--depends-on",
        "2",
        "--depends-on",
        "3",
    )
    assert task["depends_on"] == [1, 2, 3]


def test_status_update(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    _, updated = invoke("task", "update", str(task["id"]), "--status", "in_review")
    assert updated["status"] == "in_review"


def test_block_then_unblock(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    _, blocked = invoke(
        "task", "update", str(task["id"]), "--blocked-reason", "waiting on artifact"
    )
    assert blocked["blocked"] is True
    assert blocked["blocked_reason"] == "waiting on artifact"

    _, unblocked = invoke("task", "update", str(task["id"]), "--unblock")
    assert unblocked["blocked"] is False
    assert unblocked["blocked_reason"] is None


def test_block_and_unblock_are_mutually_exclusive(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, task = invoke("task", "create", "--title", "t", "--project", str(project_id))
    result, _ = invoke(
        "task", "update", str(task["id"]), "--blocked-reason", "x", "--unblock"
    )
    assert result.exit_code == 2


def test_bad_tier_enum(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "task", "create", "--title", "t", "--project", str(project_id), "--tier", "nope"
    )
    assert result.exit_code == 2


def test_list_filters_by_status(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    invoke("task", "create", "--title", "a", "--project", str(project_id))
    _, task_b = invoke("task", "create", "--title", "b", "--project", str(project_id))
    invoke("task", "update", str(task_b["id"]), "--status", "done")
    _, rows = invoke("task", "list", "--status", "backlog")
    assert [r["title"] for r in rows] == ["a"]
