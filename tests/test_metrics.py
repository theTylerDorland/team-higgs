"""metric define/report and the layered READ-ONLY trust boundary.

The boundary is defense-in-depth: a least-privilege role (primary), single-
statement extended-protocol execution, a READ ONLY transaction, and define-time
validation. These tests exercise the report-time controls by seeding hostile
definitions *directly* into the table (simulating a pre-existing or bypassed
definition), because define-time validation would otherwise reject them.
"""

from __future__ import annotations

import os

import psycopg
import pytest

# The reviewer's exact proof-of-concept.
POC_MULTI = (
    "COMMIT; BEGIN READ WRITE; "
    "INSERT INTO retros(trigger) VALUES ('pwned'); COMMIT; BEGIN;"
)
CTE_WRITE = (
    "WITH x AS (INSERT INTO retros(trigger) VALUES ('cte') RETURNING *) "
    "SELECT * FROM x"
)
# One top-level statement that bypasses SET LOCAL ROLE (RESET ROLE returns to
# session_user) and prepare=True (Parse never sees the inner EXECUTE). Only the
# READ ONLY transaction stops it — this payload pins that control.
DO_BLOCK_RESET_ROLE = (
    "DO $$ BEGIN RESET ROLE; "
    "EXECUTE 'INSERT INTO retros(trigger) VALUES (''x'')'; END $$"
)


def _seed_metric(name: str, definition: str) -> None:
    """Insert a raw definition straight into the table, bypassing the CLI's
    define-time validation, to test the report-time boundary."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "INSERT INTO metrics (name, definition, rationale) VALUES (%s, %s, %s)",
            (name, definition, "seed"),
        )


def _count(table: str) -> int:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()  # noqa: S608
    assert row is not None
    return int(row[0])


# --- define-time validation (fast-fail UX) --------------------------------


def test_define_rejects_multi_statement(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "metric", "define", "--name", "evil", "--query", POC_MULTI, "--rationale", "x"
    )
    assert result.exit_code == 2


def test_define_rejects_non_select(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke(
        "metric", "define", "--name", "d", "--query",
        "DELETE FROM projects", "--rationale", "x",
    )
    assert result.exit_code == 2


def test_define_allows_with_cte_select(invoke) -> None:  # type: ignore[no-untyped-def]
    # A read-only CTE is a legitimate WITH definition and must be accepted.
    result, _ = invoke(
        "metric", "define", "--name", "w", "--query",
        "WITH x AS (SELECT 1 AS n) SELECT * FROM x", "--rationale", "ok",
    )
    assert result.exit_code == 0


# --- happy path -----------------------------------------------------------


def test_report_runs_multi_row_select(invoke) -> None:  # type: ignore[no-untyped-def]
    invoke("project", "create", "--name", "a", "--repo", "r")
    invoke("project", "create", "--name", "b", "--repo", "r")
    invoke(
        "metric", "define", "--name", "names",
        "--query", "SELECT name FROM projects ORDER BY name",
        "--rationale", "portfolio",
    )
    _, rows = invoke("metric", "report", "--name", "names")
    assert rows == [{"name": "a"}, {"name": "b"}]


# --- report-time boundary -------------------------------------------------


def test_report_rejects_multi_statement_poc(invoke) -> None:  # type: ignore[no-untyped-def]
    _seed_metric("evil", POC_MULTI)
    result, _ = invoke("metric", "report", "--name", "evil")
    assert result.exit_code != 0
    assert _count("retros") == 0  # nothing persisted


def test_report_rejects_cte_write(invoke) -> None:  # type: ignore[no-untyped-def]
    _seed_metric("cte", CTE_WRITE)
    result, _ = invoke("metric", "report", "--name", "cte")
    assert result.exit_code != 0
    assert _count("retros") == 0


def test_report_read_only_blocks_do_block_reset_role(invoke) -> None:  # type: ignore[no-untyped-def]
    """Pin the load-bearing control: the production report path is READ ONLY,
    which blocks a DO-block payload that defeats SET LOCAL ROLE and prepare=True.
    This fails if anyone removes read_only=True from the report transaction."""
    _seed_metric("doblock", DO_BLOCK_RESET_ROLE)
    result, _ = invoke("metric", "report", "--name", "doblock")
    assert result.exit_code != 0
    assert _count("retros") == 0  # READ ONLY prevented the write


@pytest.mark.parametrize(
    "definition",
    [
        "INSERT INTO retros(trigger) VALUES ('x')",
        "DELETE FROM projects",
        "TRUNCATE projects",
        "DROP TABLE retros",
    ],
)
def test_report_rejects_single_statement_writes(invoke, definition) -> None:  # type: ignore[no-untyped-def]
    invoke("project", "create", "--name", "keep", "--repo", "r")
    _seed_metric("w", definition)
    result, _ = invoke("metric", "report", "--name", "w")
    assert result.exit_code != 0
    # State is unchanged: the seeded project survives and no retro was written.
    assert _count("projects") == 1
    assert _count("retros") == 0


def test_report_ro_role_exists_and_lacks_write() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        role = conn.execute(
            "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'emctl_report_ro'"
        ).fetchone()
        assert role is not None  # provisioned by migration 0002
        assert role[0] is False  # NOLOGIN
        # A write under the role fails even in a writable transaction.
        conn.execute("SET LOCAL ROLE emctl_report_ro")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO retros(trigger) VALUES ('x')")
        conn.rollback()


def test_report_unknown_metric_is_not_found(invoke) -> None:  # type: ignore[no-untyped-def]
    result, _ = invoke("metric", "report", "--name", "does-not-exist")
    assert result.exit_code == 3


# --- report-time boundary pins the schema-v2 tables -----------------------
# The existing hostile-write tests target `retros`; these repeat the same
# three attack shapes against the new `risks` / `task_events` tables. Each
# payload is written with valid FK values (via `SELECT ... FROM <parent>`) so
# it *would* write absent the boundary — meaning this regression fails if
# anyone ever reopens READ ONLY or grants the report role write access to the
# new tables. The `DO`-block payload defeats SET LOCAL ROLE and prepare=True,
# so only the READ ONLY transaction stops it.
_RISKS_INSERT = (
    "INSERT INTO risks (project_id, title, category, severity) "
    "SELECT id, 't', 'security', 'high' FROM projects LIMIT 1"
)
_EVENTS_INSERT = (
    "INSERT INTO task_events (task_id, to_status) "
    "SELECT id, 'in_review' FROM tasks LIMIT 1"
)
NEW_TABLE_WRITE_PAYLOADS = [
    ("risks_insert", _RISKS_INSERT, "risks"),
    (
        "risks_cte",
        f"WITH x AS ({_RISKS_INSERT} RETURNING *) SELECT * FROM x",
        "risks",
    ),
    (
        "risks_do_reset_role",
        "DO $$ BEGIN RESET ROLE; EXECUTE 'INSERT INTO risks "
        "(project_id, title, category, severity) SELECT id, ''t'', ''security'', "
        "''high'' FROM projects LIMIT 1'; END $$",
        "risks",
    ),
    ("events_insert", _EVENTS_INSERT, "task_events"),
    (
        "events_cte",
        f"WITH x AS ({_EVENTS_INSERT} RETURNING *) SELECT * FROM x",
        "task_events",
    ),
    (
        "events_do_reset_role",
        "DO $$ BEGIN RESET ROLE; EXECUTE 'INSERT INTO task_events "
        "(task_id, to_status) SELECT id, ''in_review'' FROM tasks LIMIT 1'; END $$",
        "task_events",
    ),
]


@pytest.mark.parametrize(
    "label,definition,table",
    NEW_TABLE_WRITE_PAYLOADS,
    ids=[p[0] for p in NEW_TABLE_WRITE_PAYLOADS],
)
def test_report_blocks_hostile_writes_to_new_tables(  # type: ignore[no-untyped-def]
    invoke, label, definition, table
) -> None:
    # A real project + task so the payloads reference valid FKs (and so the
    # legitimate task_events opening row is accounted for below).
    _, project = invoke("project", "create", "--name", "p", "--repo", "r")
    invoke("task", "create", "--title", "t", "--project", str(project["id"]))
    before = _count(table)  # 0 for risks; 1 for task_events (the opening event)
    _seed_metric(label, definition)
    result, _ = invoke("metric", "report", "--name", label)
    assert result.exit_code != 0
    assert _count(table) == before  # the hostile payload wrote nothing
