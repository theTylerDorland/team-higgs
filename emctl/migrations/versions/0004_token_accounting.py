"""token accounting by type: typed token columns on runs

Additive and reversible (PRD docs/prd/token-accounting.md §3). Adds four
nullable ``BIGINT`` columns to ``runs`` so per-run API token usage is recorded
by type rather than as a single lump:

* ``input_tokens``       -- uncached input tokens;
* ``output_tokens``      -- output tokens;
* ``cache_read_tokens``  -- API ``cache_read_input_tokens``;
* ``cache_write_tokens`` -- API ``cache_creation_input_tokens``.

All four default NULL, so existing rows and runs without a transcript stay
NULL and validate without a data migration. Each carries a
``col IS NULL OR col >= 0`` CHECK (token counts are never negative; NULL stays
allowed). ``token_cost`` is left untouched: it remains the legacy
rough-total/lump; the typed columns supersede it for cost projection but
nothing here rewrites it.

``downgrade()`` drops the four columns; the round-trip is tested
(``tests/test_migrate.py``).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def _nonneg_check(name: str) -> str:
    return f"runs_{name}_nonneg"


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("runs", sa.Column(name, sa.BigInteger, nullable=True))
        # Token counts are never negative; NULL stays allowed (unknown/absent).
        op.create_check_constraint(
            _nonneg_check(name), "runs", f"{name} IS NULL OR {name} >= 0"
        )


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        # Dropping the column drops its check too, but drop explicitly so the
        # reversal is symmetric and self-documenting.
        op.drop_constraint(_nonneg_check(name), "runs", type_="check")
        op.drop_column("runs", name)
