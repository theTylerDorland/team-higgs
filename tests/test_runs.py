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


def _start_run(invoke, task_id) -> int:  # type: ignore[no-untyped-def]
    _, run = invoke(
        "run", "start", "--task", str(task_id), "--role", "impl", "--model", "m",
        "--mode", "subagent",
    )
    return int(run["id"])


def test_finish_persists_typed_tokens(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    _, finished = invoke(
        "run", "finish", "--run", str(run_id), "--outcome", "done",
        "--input-tokens", "11", "--output-tokens", "22",
        "--cache-read", "333", "--cache-write", "44",
    )
    assert finished["input_tokens"] == 11
    assert finished["output_tokens"] == 22
    assert finished["cache_read_tokens"] == 333
    assert finished["cache_write_tokens"] == 44
    # Legacy lump column is untouched when not passed.
    assert finished["token_cost"] is None


def test_finish_leaves_typed_tokens_null_when_absent(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    _, finished = invoke("run", "finish", "--run", str(run_id), "--outcome", "done")
    assert finished["input_tokens"] is None
    assert finished["output_tokens"] is None
    assert finished["cache_read_tokens"] is None
    assert finished["cache_write_tokens"] is None


def test_update_amends_finished_run(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    invoke("run", "finish", "--run", str(run_id), "--outcome", "done")
    _, updated = invoke(
        "run", "update", str(run_id),
        "--input-tokens", "100", "--output-tokens", "200",
        "--cache-read", "300", "--cache-write", "400",
        "--tokens", "9", "--cost", "3.2500", "--outcome", "failed",
        "--log-ref", "log/amended",
    )
    assert updated["input_tokens"] == 100
    assert updated["output_tokens"] == 200
    assert updated["cache_read_tokens"] == 300
    assert updated["cache_write_tokens"] == 400
    assert updated["token_cost"] == 9
    assert updated["cost_usd"] == "3.2500"
    assert updated["outcome"] == "failed"
    assert updated["log_ref"] == "log/amended"
    # update is not a finish: it must not clear the existing ended_at.
    assert updated["ended_at"] is not None


def test_update_partial_leaves_other_fields(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    invoke(
        "run", "finish", "--run", str(run_id), "--outcome", "done",
        "--input-tokens", "5",
    )
    _, updated = invoke("run", "update", str(run_id), "--output-tokens", "8")
    assert updated["input_tokens"] == 5  # untouched
    assert updated["output_tokens"] == 8  # amended
    assert updated["outcome"] == "done"  # untouched


def test_update_unknown_run_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("run", "update", "9999", "--output-tokens", "1")
    assert result.exit_code == 3


def test_update_bad_outcome_is_validation_error(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    invoke("run", "finish", "--run", str(run_id), "--outcome", "done")
    result, _ = invoke("run", "update", str(run_id), "--outcome", "not-a-thing")
    assert result.exit_code == 2


def test_update_bad_cost_is_validation_error(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    invoke("run", "finish", "--run", str(run_id), "--outcome", "done")
    result, _ = invoke("run", "update", str(run_id), "--cost", "abc")
    assert result.exit_code == 2


def test_update_bad_token_value_is_validation_error(invoke, task_id) -> None:  # type: ignore[no-untyped-def]
    run_id = _start_run(invoke, task_id)
    invoke("run", "finish", "--run", str(run_id), "--outcome", "done")
    result, _ = invoke("run", "update", str(run_id), "--input-tokens", "notanint")
    assert result.exit_code == 2
