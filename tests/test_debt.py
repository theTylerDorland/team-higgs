"""debt add/resolve/merge."""

from __future__ import annotations


def _add(invoke, where: str):  # type: ignore[no-untyped-def]
    _, row = invoke(
        "debt", "add", "--where", where, "--kind", "duplication",
        "--severity", "low", "--evidence", "seen in two places",
    )
    return row


def test_merge_bumps_recurrence_and_resolves_dups(invoke) -> None:  # type: ignore[no-untyped-def]
    keeper = _add(invoke, "a.py")
    dup1 = _add(invoke, "b.py")
    dup2 = _add(invoke, "c.py")

    _, merged = invoke(
        "debt", "merge", "--into", str(keeper["id"]),
        str(dup1["id"]), str(dup2["id"]),
    )
    assert merged["recurrence"] == 3  # started at 1, +2 dups

    _, rows = invoke("debt", "list", "--status", "resolved")
    resolved_ids = {r["id"] for r in rows}
    assert resolved_ids == {dup1["id"], dup2["id"]}
    for row in rows:
        assert row["resolved_ref"] == f"merged into #{keeper['id']}"


def test_merge_into_self_is_validation_error(invoke) -> None:  # type: ignore[no-untyped-def]
    keeper = _add(invoke, "a.py")
    result, _ = invoke(
        "debt", "merge", "--into", str(keeper["id"]), str(keeper["id"])
    )
    assert result.exit_code == 2


def test_resolve_sets_ref(invoke) -> None:  # type: ignore[no-untyped-def]
    item = _add(invoke, "a.py")
    _, resolved = invoke(
        "debt", "resolve", "--debt", str(item["id"]), "--resolved-ref", "PR #5"
    )
    assert resolved["status"] == "resolved"
    assert resolved["resolved_ref"] == "PR #5"


def test_bad_kind_enum(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "debt", "add", "--where", "a.py", "--kind", "nonsense",
        "--severity", "low", "--evidence", "e",
    )
    assert result.exit_code == 2
