"""risk add/update/list/show — happy and unhappy paths (PRD §4)."""

from __future__ import annotations

import pytest


@pytest.fixture
def project_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    return int(project["id"])


def test_add_defaults_to_acknowledged(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "SET LOCAL ROLE gap",
        "--category", "security", "--severity", "medium",
    )
    assert risk["status"] == "acknowledged"
    assert risk["resolved_at"] is None
    assert risk["severity"] == "medium"


def test_add_with_links_and_actor(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, decision = invoke(
        "decision", "add", "--title", "accept it", "--decision", "live with it"
    )
    _, pr = invoke("pr", "open", "--project", str(project_id), "--github-pr", "5")
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "linked",
        "--category", "architecture", "--severity", "low", "--body", "context",
        "--decision", str(decision["id"]), "--pr", str(pr["id"]), "--by", "em",
    )
    assert risk["decision_id"] == decision["id"]
    assert risk["pr_id"] == pr["id"]
    assert risk["acknowledged_by"] == "em"


def test_update_off_acknowledged_sets_resolved_at(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "cost", "--severity", "high",
    )
    _, updated = invoke(
        "risk", "update", str(risk["id"]), "--status", "accepted",
        "--mitigation", "we live with it",
    )
    assert updated["status"] == "accepted"
    assert updated["resolved_at"] is not None
    assert updated["mitigation"] == "we live with it"


def test_reopen_clears_resolved_at(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "security", "--severity", "high",
    )
    # acknowledged -> mitigated stamps resolved_at ...
    _, mitigated = invoke("risk", "update", str(risk["id"]), "--status", "mitigated")
    assert mitigated["resolved_at"] is not None
    # ... and reopening (mitigated -> acknowledged) clears it back to NULL.
    _, reopened = invoke("risk", "update", str(risk["id"]), "--status", "acknowledged")
    assert reopened["status"] == "acknowledged"
    assert reopened["resolved_at"] is None


def test_add_already_dispositioned_sets_resolved_at(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "born-accepted",
        "--category", "operational", "--severity", "low", "--status", "accepted",
    )
    assert risk["status"] == "accepted"
    assert risk["resolved_at"] is not None


def test_list_filters(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    invoke(
        "risk", "add", "--project", str(project_id), "--title", "a",
        "--category", "security", "--severity", "high",
    )
    invoke(
        "risk", "add", "--project", str(project_id), "--title", "b",
        "--category", "cost", "--severity", "low",
    )
    _, rows = invoke("risk", "list", "--category", "security")
    assert [r["title"] for r in rows] == ["a"]
    _, by_sev = invoke("risk", "list", "--severity", "low")
    assert [r["title"] for r in by_sev] == ["b"]


def test_show_includes_linked_decision_and_pr(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, decision = invoke(
        "decision", "add", "--title", "d", "--decision", "x"
    )
    _, pr = invoke("pr", "open", "--project", str(project_id), "--github-pr", "6")
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "dependency", "--severity", "medium",
        "--decision", str(decision["id"]), "--pr", str(pr["id"]),
    )
    _, shown = invoke("risk", "show", str(risk["id"]))
    assert shown["linked_decision"]["id"] == decision["id"]
    assert shown["linked_pr"]["id"] == pr["id"]


def test_show_without_links_is_none(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, risk = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "product", "--severity", "low",
    )
    _, shown = invoke("risk", "show", str(risk["id"]))
    assert shown["linked_decision"] is None
    assert shown["linked_pr"] is None


# --- unhappy paths --------------------------------------------------------


def test_bad_category_enum_is_exit_2(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "not-a-category", "--severity", "high",
    )
    assert result.exit_code == 2


def test_bad_severity_enum_is_exit_2(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "security", "--severity", "critical",
    )
    assert result.exit_code == 2


def test_missing_project_fk_is_conflict(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "risk", "add", "--project", "9999", "--title", "t",
        "--category", "security", "--severity", "high",
    )
    assert result.exit_code == 4


def test_missing_decision_fk_is_conflict(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "risk", "add", "--project", str(project_id), "--title", "t",
        "--category", "security", "--severity", "high", "--decision", "9999",
    )
    assert result.exit_code == 4


def test_update_unknown_risk_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("risk", "update", "9999", "--status", "mitigated")
    assert result.exit_code == 3


def test_show_unknown_risk_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("risk", "show", "9999")
    assert result.exit_code == 3
