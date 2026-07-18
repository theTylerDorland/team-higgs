"""Helpers shared by command modules: reading input files into values."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emctl.errors import ValidationError


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"cannot read file: {path}") from exc


def read_json_file(path: Path) -> Any:
    text = read_text_file(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc.msg}") from exc
