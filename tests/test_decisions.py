"""decision add (significance/status), supersede, and list filters (PRD §4)."""

from __future__ import annotations


def test_add_defaults_major_accepted(invoke) -> None:  # type: ignore[no-untyped-def]
    _, d = invoke("decision", "add", "--title", "t", "--decision", "x")
    assert d["significance"] == "major"
    assert d["status"] == "accepted"
    assert d["superseded_by"] is None


def test_add_minor_proposed(invoke) -> None:  # type: ignore[no-untyped-def]
    _, d = invoke(
        "decision", "add", "--title", "routine", "--decision", "x",
        "--significance", "minor", "--status", "proposed",
    )
    assert d["significance"] == "minor"
    assert d["status"] == "proposed"


def test_supersede_sets_both_sides(invoke) -> None:  # type: ignore[no-untyped-def]
    _, old = invoke("decision", "add", "--title", "old", "--decision", "v1")
    _, new = invoke("decision", "add", "--title", "new", "--decision", "v2")
    _, superseded = invoke(
        "decision", "supersede", str(old["id"]), "--by", str(new["id"])
    )
    assert superseded["status"] == "superseded"
    assert superseded["superseded_by"] == new["id"]


def test_supersede_self_is_validation_error(invoke) -> None:  # type: ignore[no-untyped-def]
    _, d = invoke("decision", "add", "--title", "d", "--decision", "x")
    result, _ = invoke("decision", "supersede", str(d["id"]), "--by", str(d["id"]))
    assert result.exit_code == 2


def test_supersede_unknown_new_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    _, old = invoke("decision", "add", "--title", "old", "--decision", "x")
    result, _ = invoke("decision", "supersede", str(old["id"]), "--by", "9999")
    assert result.exit_code == 3


def test_supersede_unknown_old_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    _, new = invoke("decision", "add", "--title", "new", "--decision", "x")
    result, _ = invoke("decision", "supersede", "9999", "--by", str(new["id"]))
    assert result.exit_code == 3


def test_list_filters_by_significance_and_status(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke("decision", "add", "--title", "major", "--decision", "x")
    invoke(
        "decision", "add", "--title", "minor", "--decision", "x",
        "--significance", "minor",
    )
    _, majors = invoke("decision", "list", "--significance", "major")
    assert [d["title"] for d in majors] == ["major"]

    _, old = invoke("decision", "add", "--title", "old", "--decision", "x")
    _, new = invoke("decision", "add", "--title", "new", "--decision", "x")
    invoke("decision", "supersede", str(old["id"]), "--by", str(new["id"]))
    _, superseded = invoke("decision", "list", "--status", "superseded")
    assert [d["title"] for d in superseded] == ["old"]


def test_bad_significance_enum_is_exit_2(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "decision", "add", "--title", "t", "--decision", "x",
        "--significance", "huge",
    )
    assert result.exit_code == 2
