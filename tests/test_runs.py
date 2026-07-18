"""run start -> finish, including finish by --task."""

from __future__ import annotations

import pytest


@pytest.fixture
def task_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    _, task = invoke("task", "create", "--title", "t", "--project", str(project["id"]))
    return int(task["id"])


def test_finish_by_run_id_sets_fields(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    _, run = invoke(
        "run", "start", "--task", str(task_id), "--role", "impl", "--model", "m",
        "--mode", "subagent",
    )
    assert run["ended_at"] is None
    _, finished = invoke(
        "run", "finish", "--run", str(run["id"]), "--outcome", "done",
        "--tokens", "42", "--cost", "1.5000", "--log-ref", "log/x",
    )
    assert finished["ended_at"] is not None
    assert finished["outcome"] == "done"
    assert finished["token_cost"] == 42
    assert finished["cost_usd"] == "1.5000"
    assert finished["log_ref"] == "log/x"


def test_finish_by_task_picks_latest_open_run(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    _, first = invoke(
        "run", "start", "--task", str(task_id), "--role", "impl", "--model", "m",
        "--mode", "subagent",
    )
    invoke("run", "finish", "--run", str(first["id"]), "--outcome", "done")
    _, second = invoke(
        "run", "start", "--task", str(task_id), "--role", "impl", "--model", "m",
        "--mode", "subagent",
    )
    _, finished = invoke(
        "run", "finish", "--task", str(task_id), "--outcome", "blocked"
    )
    assert finished["id"] == second["id"]
    assert finished["outcome"] == "blocked"


def test_finish_without_run_or_task_is_validation_error(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("run", "finish", "--outcome", "done")
    assert result.exit_code == 2


def test_finish_with_no_open_run_is_not_found(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("run", "finish", "--task", str(task_id), "--outcome", "done")
    assert result.exit_code == 3
