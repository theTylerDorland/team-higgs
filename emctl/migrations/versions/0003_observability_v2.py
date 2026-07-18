"""observability schema v2: risks, task_events, decision/pr link-ups

Additive and reversible (PRD docs/prd/observability.md §3, §5):

* new ``risks`` register table (FKs to projects/decisions/prs);
* new ``task_events`` status-history table (FK to tasks) + its index;
* ``decisions`` gains ``status`` / ``significance`` / ``superseded_by``;
* ``prs`` gains ``task_id`` (link to the task a PR implements);
* partial ``idx_risks_open`` + ``idx_task_events_task`` indexes.

New columns are nullable or carry safe ``NOT NULL DEFAULT`` values, so existing
rows validate without a data migration. One *generic* backfill step seeds a
single synthetic ``task_events`` row per pre-existing task (``to_status`` =
current status, ``actor='backfill'``) so cycle-time queries do not null out;
it applies to any database and hard-codes no ids. Platform-specific backfill
(linking PR #5 to task #1, seeding this loop's risks) is an EM post-merge pass,
not this migration's job.

``emctl_report_ro`` (migration 0002) reads the new tables through the
``ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES`` set there: the new
tables are created by the same migrating role, so the default grant covers
them. A test asserts the role can SELECT both new tables.

``downgrade()`` drops the added indexes, tables, and columns in FK-safe order
(dependents before dependencies) and is tested by the round-trip.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = sa.text("now()")

    # --- decisions upgrade (ALTER, additive) ------------------------------
    op.add_column(
        "decisions",
        sa.Column(
            "status", sa.Text, nullable=False, server_default=sa.text("'accepted'")
        ),
    )
    op.add_column(
        "decisions",
        sa.Column(
            "significance",
            sa.Text,
            nullable=False,
            server_default=sa.text("'major'"),
        ),
    )
    op.add_column(
        "decisions",
        sa.Column("superseded_by", sa.Integer, sa.ForeignKey("decisions.id")),
    )
    op.create_check_constraint(
        "decisions_status_check",
        "decisions",
        "status IN ('proposed','accepted','superseded','reversed')",
    )
    op.create_check_constraint(
        "decisions_significance_check",
        "decisions",
        "significance IN ('major','minor')",
    )

    # --- prs.task_id (ALTER, additive, nullable) --------------------------
    op.add_column(
        "prs", sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"))
    )

    # --- new risks register ----------------------------------------------
    op.create_table(
        "risks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'acknowledged'"),
        ),
        sa.Column("mitigation", sa.Text),
        sa.Column("decision_id", sa.Integer, sa.ForeignKey("decisions.id")),
        sa.Column("pr_id", sa.Integer, sa.ForeignKey("prs.id")),
        sa.Column("acknowledged_by", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "category IN ('security','architecture','operational',"
            "'cost','dependency','product')",
            name="risks_category_check",
        ),
        sa.CheckConstraint(
            "severity IN ('high','medium','low')",
            name="risks_severity_check",
        ),
        sa.CheckConstraint(
            "status IN ('acknowledged','mitigated','accepted','realized','closed')",
            name="risks_status_check",
        ),
    )

    # --- new task_events status history -----------------------------------
    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=False
        ),
        sa.Column("from_status", sa.Text),
        sa.Column("to_status", sa.Text, nullable=False),
        sa.Column("actor", sa.Text),
        sa.Column(
            "at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
    )

    op.create_index(
        "idx_risks_open",
        "risks",
        ["status"],
        postgresql_where=sa.text("status = 'acknowledged'"),
    )
    op.create_index("idx_task_events_task", "task_events", ["task_id"])

    # --- generic backfill: one synthetic event per pre-existing task ------
    # No hard-coded ids; a no-op on a fresh database. from_status stays NULL
    # (origin unknown), actor marks it as synthetic so cycle-time queries have
    # a terminal event to anchor on.
    op.execute(
        "INSERT INTO task_events (task_id, from_status, to_status, actor) "
        "SELECT id, NULL, status, 'backfill' FROM tasks"
    )


def downgrade() -> None:
    # FK-safe order: drop dependents (new tables + indexes) before the columns
    # and tables they reference.
    op.drop_index("idx_task_events_task", table_name="task_events")
    op.drop_index("idx_risks_open", table_name="risks")
    op.drop_table("risks")
    op.drop_table("task_events")

    op.drop_column("prs", "task_id")

    op.drop_constraint("decisions_significance_check", "decisions")
    op.drop_constraint("decisions_status_check", "decisions")
    op.drop_column("decisions", "superseded_by")
    op.drop_column("decisions", "significance")
    op.drop_column("decisions", "status")
