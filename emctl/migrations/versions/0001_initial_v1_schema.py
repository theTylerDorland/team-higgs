"""initial v1 schema

Faithfully reproduces db/schema.sql: all 12 tables, every CHECK constraint,
defaults (including depends_on '{}' and JSONB '[]'), the 5 indexes, UNIQUE
constraints, and FKs. This migration — not db/schema.sql — is the operative
schema truth going forward.

Revision ID: 0001
Revises:
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = sa.text("now()")

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("repo", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("brief", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "status IN ('active','paused','done','archived')",
            name="projects_status_check",
        ),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("spec", sa.Text),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'backlog'"),
        ),
        sa.Column(
            "blocked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("blocked_reason", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column(
            "model_tier",
            sa.Text,
            nullable=False,
            server_default=sa.text("'execute'"),
        ),
        sa.Column("prd_ref", sa.Text),
        sa.Column("branch", sa.Text),
        sa.Column(
            "depends_on",
            postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "status IN ('backlog','planned','in_progress',"
            "'in_review','awaiting_tyler','done')",
            name="tasks_status_check",
        ),
        sa.CheckConstraint(
            "model_tier IN ('plan','execute','local')",
            name="tasks_model_tier_check",
        ),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id")),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("outcome", sa.Text),
        sa.Column("token_cost", sa.BigInteger),
        sa.Column("cost_usd", sa.Numeric(10, 4)),
        sa.Column("log_ref", sa.Text),
        sa.CheckConstraint(
            "mode IN ('team','subagent','headless','interactive')",
            name="runs_mode_check",
        ),
        sa.CheckConstraint(
            "outcome IN ('done','negative-result','blocked','failed')",
            name="runs_outcome_check",
        ),
    )

    op.create_table(
        "prs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("github_pr", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("risk_level", sa.Text),
        sa.Column("em_summary", sa.Text),
        sa.Column("tyler_decision", sa.Text),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('open','merged','rejected','closed')",
            name="prs_status_check",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low','medium','high')",
            name="prs_risk_level_check",
        ),
        sa.UniqueConstraint(
            "project_id", "github_pr", name="prs_project_id_github_pr_key"
        ),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "pr_id", sa.Integer, sa.ForeignKey("prs.id"), nullable=False
        ),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("model", sa.Text),
        sa.Column("verdict", sa.Text, nullable=False),
        sa.Column(
            "findings",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("strongest_objection", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "verdict IN ('approve','concerns','block')",
            name="reviews_verdict_check",
        ),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id")),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "blocking",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("answer", sa.Text),
        sa.Column("answered_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("context", sa.Text),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id")),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'proposed'"),
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.CheckConstraint(
            "type IN ('mockup','diagram','spec','schema',"
            "'model','eval-set','prompt')",
            name="artifacts_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','approved','rejected','superseded')",
            name="artifacts_status_check",
        ),
    )

    op.create_table(
        "learnings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("observation", sa.Text, nullable=False),
        sa.Column("evidence", sa.Text),
        sa.Column("filed_by", sa.Text),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("retro_id", sa.Integer),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "category IN ('start','stop','keep','question')",
            name="learnings_category_check",
        ),
        sa.CheckConstraint(
            "status IN ('open','resolved','escalated')",
            name="learnings_status_check",
        ),
    )

    op.create_table(
        "debt",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id")),
        sa.Column("location", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("filed_by", sa.Text),
        sa.Column(
            "recurrence",
            sa.Integer,
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "passes_survived",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("resolved_ref", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "kind IN ('duplication','coupling','missing-tests',"
            "'pattern-drift','dead-code','docs','other')",
            name="debt_kind_check",
        ),
        sa.CheckConstraint(
            "severity IN ('high','medium','low')",
            name="debt_severity_check",
        ),
        sa.CheckConstraint(
            "status IN ('open','proposed','resolved','stale','escalated')",
            name="debt_status_check",
        ),
    )

    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("definition", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.CheckConstraint(
            "status IN ('proposed','active','retired')",
            name="metrics_status_check",
        ),
    )

    op.create_table(
        "retros",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("doc_path", sa.Text),
        sa.Column(
            "opened_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_index(
        "idx_tasks_status",
        "tasks",
        ["status"],
        postgresql_where=sa.text("status != 'done'"),
    )
    op.create_index("idx_runs_task", "runs", ["task_id"])
    op.create_index("idx_reviews_pr", "reviews", ["pr_id"])
    op.create_index(
        "idx_debt_open",
        "debt",
        ["status"],
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index(
        "idx_learnings_open",
        "learnings",
        ["status"],
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("idx_learnings_open", table_name="learnings")
    op.drop_index("idx_debt_open", table_name="debt")
    op.drop_index("idx_reviews_pr", table_name="reviews")
    op.drop_index("idx_runs_task", table_name="runs")
    op.drop_index("idx_tasks_status", table_name="tasks")

    op.drop_table("retros")
    op.drop_table("metrics")
    op.drop_table("debt")
    op.drop_table("learnings")
    op.drop_table("artifacts")
    op.drop_table("decisions")
    op.drop_table("questions")
    op.drop_table("reviews")
    op.drop_table("prs")
    op.drop_table("runs")
    op.drop_table("tasks")
    op.drop_table("projects")
