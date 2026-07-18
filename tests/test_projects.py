"""project create/show/list and its unhappy paths."""

from __future__ import annotations


def test_create_list_show_happy(invoke) -> None:  # type: ignore[no-untyped-def]
    _, created = invoke("project", "create", "--name", "alpha", "--repo", "r")
    assert created["name"] == "alpha"
    assert created["status"] == "active"

    _, rows = invoke("project", "list")
    assert [r["name"] for r in rows] == ["alpha"]

    _, by_id = invoke("project", "show", str(created["id"]))
    assert by_id["id"] == created["id"]

    _, by_name = invoke("project", "show", "alpha")
    assert by_name["id"] == created["id"]


def test_duplicate_name_is_conflict(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke("project", "create", "--name", "dup", "--repo", "r")
    result, _ = invoke("project", "create", "--name", "dup", "--repo", "r")
    assert result.exit_code == 4


def test_unknown_id_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("project", "show", "999")
    assert result.exit_code == 3


def test_bad_status_enum_is_validation_error(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "project", "create", "--name", "x", "--repo", "r", "--status", "bogus"
    )
    assert result.exit_code == 2
