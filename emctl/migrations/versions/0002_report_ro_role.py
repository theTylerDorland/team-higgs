"""metric-report least-privilege role

Provisions the NOLOGIN role ``emctl_report_ro`` used as the primary boundary
for ``metric report``: it may read every app table but holds no
INSERT/UPDATE/DELETE/TRUNCATE/CREATE privilege. ALTER DEFAULT PRIVILEGES keeps
future tables covered. The report path does ``SET LOCAL ROLE emctl_report_ro``
before executing a stored definition, so a mistaken or hostile definition runs
with no write capability at all (see emctl/repo/metrics.py).

NOLOGIN + SET ROLE is deliberate: no new credentials or secrets. The role is a
cluster-global object; grants and default privileges are per-database and are
(re)applied wherever ``emctl migrate`` runs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "emctl_report_ro"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}'
            ) THEN
                CREATE ROLE {ROLE} NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT ON TABLES TO {ROLE}"
    )
    # Let the (possibly non-superuser) migrating role SET ROLE to it without
    # extra credentials. Harmless for the superuser dev role.
    op.execute(f"GRANT {ROLE} TO CURRENT_USER")


def downgrade() -> None:
    # Reverse only what this migration granted *in this database*. We do NOT
    # drop the role: it is a cluster-global object and other databases in the
    # same cluster may still depend on it (Postgres blocks a DROP ROLE while any
    # database holds grants for it). Dropping it is an operator action once no
    # database references it, not a per-database migration's job. The leftover
    # role is a harmless NOLOGIN principal with no privileges here after this.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT ON TABLES FROM {ROLE}"
    )
    op.execute(f"REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
