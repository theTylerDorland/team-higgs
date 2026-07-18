#!/usr/bin/env python3
"""Aggregate per-type token usage from a Claude Code agent transcript.

Standalone on purpose: ``emctl`` stays format-agnostic (it takes the four token
numbers via flags), so all coupling to the Claude-Code transcript format lives
in this one file. A format change touches here, not the state CLI.

Input is a JSONL transcript -- one message object per line. The API ``usage``
block lives at ``message.usage`` with keys ``input_tokens``, ``output_tokens``,
``cache_read_input_tokens`` and ``cache_creation_input_tokens``. This tool sums
those four across every line that carries a ``usage`` and reports them under the
emctl column names (``cache_read_tokens`` / ``cache_write_tokens``), plus the
``message.model`` if any line carries one (last non-empty value wins).

Contract: pure read. It opens exactly one file read-only, parses it tolerantly
(unparseable lines and lines without a ``usage`` are skipped; a malformed
transcript never raises), and prints the four sums and the model as sorted JSON
to stdout. It writes nothing, executes nothing, and makes no network call.

Usage:
    python tools/agent_token_split.py <transcript.jsonl>

The EM pipes the result into ``emctl run finish``/``run update``:
    --input-tokens --output-tokens --cache-read --cache-write
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# API usage key -> emctl/DB column name.
_USAGE_KEYS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_input_tokens": "cache_read_tokens",
    "cache_creation_input_tokens": "cache_write_tokens",
}


def _as_int(value: Any) -> int:
    """A usage entry contributes only if it is a real integer token count.

    Bools are ints in Python but are never valid counts, so they are ignored.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def aggregate(lines: list[str]) -> dict[str, Any]:
    """Sum the four token types over ``lines``; surface the model if present.

    Tolerant by construction: a line that is not JSON, is not an object, or
    carries no ``message.usage`` mapping is skipped rather than raised on.
    """
    totals = {col: 0 for col in _USAGE_KEYS.values()}
    model: str | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        message = obj.get("message")
        if not isinstance(message, dict):
            continue
        seen_model = message.get("model")
        if isinstance(seen_model, str) and seen_model:
            model = seen_model
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        for api_key, column in _USAGE_KEYS.items():
            totals[column] += _as_int(usage.get(api_key))

    result: dict[str, Any] = dict(totals)
    result["model"] = model
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate per-type token usage from an agent transcript."
    )
    parser.add_argument("transcript", help="Path to a JSONL transcript.")
    args = parser.parse_args(argv)

    try:
        with open(args.transcript, encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError as exc:
        # Not a malformed-transcript case (that never raises); this is a bad
        # invocation. Report cleanly on stderr, no traceback, non-zero exit.
        print(f"cannot read transcript: {exc}", file=sys.stderr)
        return 1

    result = aggregate(lines)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
