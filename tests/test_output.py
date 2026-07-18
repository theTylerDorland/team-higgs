"""Output contract: deterministic JSON, ISO-8601 timestamps, clean table."""

from __future__ import annotations

import json
import re


def test_json_is_sorted_and_parseable(invoke) -> None:  # type: ignore[no-untyped-def]
    result, parsed = invoke("project", "create", "--name", "z", "--repo", "r")
    assert result.exit_code == 0
    # Keys are emitted sorted for stable diffs.
    keys = list(parsed.keys())
    assert keys == sorted(keys)
    # Round-trips cleanly.
    assert json.loads(result.output) == parsed


def test_timestamps_are_iso8601_utc(invoke) -> None:  # type: ignore[no-untyped-def]
    _, project = invoke("project", "create", "--name", "z", "--repo", "r")
    created = project["created_at"]
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*\+00:00", created)


def test_table_mode_has_no_json_braces(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke("project", "create", "--name", "z", "--repo", "r")
    result, _ = invoke("project", "list", json_mode=False)
    assert result.exit_code == 0
    assert "name" in result.output
    assert not result.output.lstrip().startswith("{")
