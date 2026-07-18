"""Config and error-path exit codes."""

from __future__ import annotations

import pytest


def test_unset_database_url_is_config_error(
    invoke, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result, _ = invoke("project", "list")
    assert result.exit_code == 5


def test_migrate_without_database_url_is_config_error(
    invoke, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result, _ = invoke("migrate")
    assert result.exit_code == 5
