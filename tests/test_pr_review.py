"""pr open/update with --summary-file, review add with --findings-file."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_id(invoke) -> int:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    return int(project["id"])


def test_pr_open_and_duplicate_is_conflict(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, pr = invoke(
        "pr", "open", "--project", str(project_id), "--github-pr", "7", "--risk", "high"
    )
    assert pr["github_pr"] == 7
    assert pr["risk_level"] == "high"
    result, _ = invoke(
        "pr", "open", "--project", str(project_id), "--github-pr", "7"
    )
    assert result.exit_code == 4


def test_summary_file_ingested(invoke, project_id, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    summary = tmp_path / "summary.md"
    summary.write_text("full synthesized report", encoding="utf-8")
    _, pr = invoke(
        "pr", "open", "--project", str(project_id), "--github-pr", "8",
        "--summary-file", str(summary),
    )
    assert pr["em_summary"] == "full synthesized report"


def test_missing_summary_file_is_validation_error(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "pr", "open", "--project", str(project_id), "--github-pr", "9",
        "--summary-file", "/no/such/file.md",
    )
    assert result.exit_code == 2


def test_review_findings_file_ingested(invoke, project_id, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _, pr = invoke("pr", "open", "--project", str(project_id), "--github-pr", "10")
    findings = tmp_path / "findings.json"
    findings.write_text(
        '[{"severity":"high","where":"db.py","claim":"c",'
        '"evidence":"e","why":"w","fix":"f"}]',
        encoding="utf-8",
    )
    _, review = invoke(
        "review", "add", "--pr", str(pr["id"]), "--role", "reviewer-security",
        "--verdict", "block", "--objection", "obj", "--findings-file", str(findings),
    )
    assert review["findings"][0]["where"] == "db.py"
    assert review["verdict"] == "block"


def test_malformed_findings_json_is_validation_error(
    invoke, project_id, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    _, pr = invoke("pr", "open", "--project", str(project_id), "--github-pr", "11")
    findings = tmp_path / "bad.json"
    findings.write_text("{not valid json", encoding="utf-8")
    result, _ = invoke(
        "review", "add", "--pr", str(pr["id"]), "--role", "r",
        "--verdict", "approve", "--objection", "o", "--findings-file", str(findings),
    )
    assert result.exit_code == 2


def test_pr_update_decision_sets_decided_at(invoke, project_id) -> None:  # type: ignore[no-untyped-def]
    _, pr = invoke("pr", "open", "--project", str(project_id), "--github-pr", "12")
    _, updated = invoke(
        "pr", "update", str(pr["id"]), "--status", "merged", "--decision", "merge it"
    )
    assert updated["status"] == "merged"
    assert updated["tyler_decision"] == "merge it"
    assert updated["decided_at"] is not None
