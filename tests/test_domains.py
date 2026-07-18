"""Create/list coverage for the remaining command groups."""

from __future__ import annotations


def test_question_add_answer_list(invoke) -> None:  # type: ignore[no-untyped-def]
    _, q = invoke("question", "add", "--body", "why?", "--blocking")
    assert q["blocking"] is True
    _, answered = invoke(
        "question", "answer", "--question", str(q["id"]), "--answer", "because"
    )
    assert answered["answer"] == "because"
    assert answered["answered_at"] is not None
    # Answered blocker no longer shows under the blocking filter.
    _, blockers = invoke("question", "list", "--blocking")
    assert blockers == []


def test_decision_add_list(invoke) -> None:  # type: ignore[no-untyped-def]
    _, d = invoke(
        "decision", "add", "--title", "use alembic",
        "--context", "two schema sources", "--decision", "migrations win",
    )
    assert d["title"] == "use alembic"
    _, rows = invoke("decision", "list")
    assert len(rows) == 1


def test_artifact_create_decide_list(invoke) -> None:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    _, art = invoke(
        "artifact", "create", "--project", str(project["id"]),
        "--type", "spec", "--path", "docs/spec.md",
    )
    assert art["status"] == "proposed"
    _, decided = invoke(
        "artifact", "decide", "--artifact", str(art["id"]),
        "--status", "approved", "--notes", "looks good",
    )
    assert decided["status"] == "approved"
    assert decided["decided_at"] is not None


def test_learning_add_resolve(invoke) -> None:  # type: ignore[no-untyped-def]
    _, retro = invoke("retro", "open", "--trigger", "cadence")
    _, learning = invoke(
        "learning", "add", "--category", "keep",
        "--observation", "the loop works", "--role", "em",
    )
    assert learning["filed_by"] == "em"
    _, resolved = invoke(
        "learning", "resolve", "--learning", str(learning["id"]),
        "--retro", str(retro["id"]),
    )
    assert resolved["status"] == "resolved"
    assert resolved["retro_id"] == retro["id"]


def test_retro_open_close_list(invoke) -> None:  # type: ignore[no-untyped-def]
    _, retro = invoke("retro", "open", "--trigger", "metric trend", "--doc-path", "d")
    assert retro["closed_at"] is None
    _, closed = invoke("retro", "close", "--retro", str(retro["id"]))
    assert closed["closed_at"] is not None
    _, rows = invoke("retro", "list")
    assert len(rows) == 1
