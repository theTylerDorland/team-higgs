"""Standalone transcript aggregator (tools/agent_token_split.py).

No DB: the tool is a pure file reader. Covers the happy aggregation, the
tolerance contract (malformed line + usage-less line never raise), the model
surfacing, and a missing file reporting cleanly instead of tracing back.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_tool() -> ModuleType:
    path = _ROOT / "tools" / "agent_token_split.py"
    spec = importlib.util.spec_from_file_location("agent_token_split", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load_tool()


def _lines(name: str) -> list[str]:
    return (_FIXTURES / name).read_text().splitlines()


def test_clean_transcript_sums_by_type() -> None:
    result = tool.aggregate(_lines("transcript_clean.jsonl"))
    assert result == {
        "input_tokens": 13,
        "output_tokens": 12,
        "cache_read_tokens": 150,
        "cache_write_tokens": 20,
        "model": "claude-opus-4-8",
    }


def test_messy_transcript_is_tolerant() -> None:
    # A malformed line, a usage-less line, a non-object message, a JSON array,
    # a blank line, and a usage with non-int values are all skipped/zeroed;
    # only the one well-formed usage line counts. Never raises.
    result = tool.aggregate(_lines("transcript_messy.jsonl"))
    assert result == {
        "input_tokens": 1,
        "output_tokens": 2,
        "cache_read_tokens": 3,
        "cache_write_tokens": 4,
        "model": "claude-sonnet-5",
    }


def test_empty_input_yields_zeroes_and_null_model() -> None:
    assert tool.aggregate([]) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "model": None,
    }


def test_main_prints_sorted_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = tool.main([str(_FIXTURES / "transcript_clean.jsonl")])
    assert code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["input_tokens"] == 13
    assert parsed["cache_read_tokens"] == 150
    assert parsed["model"] == "claude-opus-4-8"


def test_main_missing_file_reports_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = tool.main([str(_FIXTURES / "does_not_exist.jsonl")])
    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout stays clean
    assert "cannot read transcript" in captured.err
