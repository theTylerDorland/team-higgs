# Backend stack

Authoritative for backend/CLI work. Drafted with `emctl` (BOOTSTRAP task 1);
extend it as the surface grows. Where this doc and a charter disagree, the
charter wins.

## Stack

- **Python 3.12+**, one `pyproject.toml` at the repo root. `emctl` ships a
  console-script entry point and runs as `python -m emctl`.
- **Typer** for the CLI: typed subcommands, generated `--help`, a global
  `--json`. Enum flags are validated by Typer against the schema's CHECK
  values, so a bad `--status`/`--verdict`/`--outcome` is rejected with the
  valid list (exit 2) before any DB round-trip.
- **psycopg 3** as the driver. Every query is parameterized: values travel as
  placeholders and identifiers are composed with `psycopg.sql` (see
  `emctl/repo/_sql.py`). No SQL is assembled by string concatenation or
  f-strings anywhere, including tests. This is a security-blocker definition.
- **Alembic** for migrations (see below). Alembic runs on SQLAlchemy, which is
  therefore a direct dependency: `emctl/migrations/env.py` builds a
  `postgresql+psycopg` engine from `DATABASE_URL`. Application queries do not
  use SQLAlchemy — they go straight through psycopg 3.
- **ruff** (lint), **mypy** (strict; no bare `dict`/`Any` on public seams),
  **pytest** (tests, real Postgres). All three must pass clean.
- New dependencies beyond these require justification in the PR.

### Layering

`commands/*` (parse + validate, one transaction, render) → `repo/*` (typed,
parameterized SQL, no printing, no env reads) → `db.py` (connection +
transaction lifecycle) and `output.py` (all rendering) and `errors.py`
(exit-code mapping). A command file reads top-to-bottom without opening the
others.

### Config, errors, output

- **Config.** The app reads exactly one connection string, `DATABASE_URL`
  (unset → `ConfigError`, exit 5). `DATABASE_URL_TEST` exists only so the test
  harness can point the app at a throwaway DB; application code never reads it.
  No connection literals live in the codebase.
- **Errors & exit codes.** `EmctlError` (exit 1) with `ConfigError`=5,
  `ValidationError`=2, `NotFoundError`=3, `ConflictError`=4. psycopg
  `UniqueViolation`/`ForeignKeyViolation` → `ConflictError`,
  `CheckViolation` → `ValidationError`. Errors subclass `click.ClickException`,
  so a clean `Error: <message>` goes to **stderr** with the mapped code. Raw
  SQL, tracebacks, and connection strings never reach stdout or stderr.
- **Output.** Human tables by default; `--json` (global, on the root app)
  switches every command to deterministic (key-sorted) JSON on stdout and
  nothing else. Timestamps are ISO-8601 in UTC.

## `metric report` trust boundary

`metric report` executes the stored `definition` of a metric — operator-authored
SQL written by the EM via `metric define`. It is trusted input, not external
data, but it is treated as fallible and constrained by layered controls. Two
independent security reviews probed this path; the accurate ordering by
importance is:

1. **READ ONLY transaction — the load-bearing, role-independent control.**
   `transaction(read_only=True)` (`emctl/db.py`, opened in
   `emctl/commands/metric.py::report`). This is the control that actually
   prevents writes, and it holds against *every* payload a review threw at it —
   including writes inside PL/pgSQL `DO` blocks and VOLATILE / SECURITY DEFINER
   functions. **Do not remove it**; a load-bearing comment marks both the site
   and the call site.
2. **Define-time validation (single `SELECT`/`WITH`) — the gate.**
   `metric define`/`update` reject anything that is not a single read query
   (after stripping comments), so multi-statement, `DO`-block, and non-read
   payloads never reach `metrics.definition` through the CLI in the first place.
   (A read-only CTE is allowed; a CTE that writes is stopped at report time by
   layer 1.)
3. **Supplementary hardening — not a boundary.** `SET LOCAL ROLE
   emctl_report_ro` (migration `0002`: a NOLOGIN role with `USAGE` + `SELECT` on
   all tables, `ALTER DEFAULT PRIVILEGES ... GRANT SELECT` for future tables, no
   write/DDL) plus prepared-statement execution
   (`conn.execute(definition, prepare=True)` → extended protocol, so the server
   rejects `;`-separated multi-statement input at Parse). These stop accidental
   and simple writes and raise the bar, but they are **bypassable within a
   single statement**: `DO $$ BEGIN RESET ROLE; EXECUTE 'INSERT …'; END $$` is
   one top-level statement (Parse never sees the inner write) and `RESET ROLE`
   returns to `session_user` (Postgres checks SET/RESET ROLE against
   `session_user`, not the active role), restoring privilege. With a writable
   transaction that payload writes; only layer 1 stops it. Making the role a
   genuine boundary (authenticating the report connection *as*
   `emctl_report_ro` so `RESET ROLE` cannot restore privilege) is deferred
   hardening, tracked as debt. (Note: passing an empty params sequence does
   **not** force the extended protocol in psycopg 3; `prepare=True` does.)

Tests seed hostile definitions directly into the table (bypassing define-time
validation) and assert the report path — on the real `read_only=True` path —
rejects the reviewer's multi-statement PoC, a CTE-write, a **`DO`-block
`RESET ROLE` + `EXECUTE INSERT`** payload, and direct
`INSERT`/`DELETE`/`TRUNCATE`/`DROP`, each with **zero** state change. The
`DO`-block test specifically pins layer 1: it fails if anyone removes the READ
ONLY transaction. The `emctl_report_ro` role is cluster-global; grants are
per-database and are (re)applied wherever `emctl migrate` runs. `0002`'s
downgrade revokes this database's grants but does not drop the role (a cluster
object other databases may depend on).

## Migrations are the operative schema truth

Two schema sources drift, so migrations win over `db/schema.sql`:

- `emctl/migrations/versions/0001_initial_v1_schema.py` faithfully reproduces
  `db/schema.sql` — all tables, CHECK constraints, defaults (`depends_on '{}'`,
  JSONB `'[]'`), indexes (including the partial ones), UNIQUE constraints, and
  FKs — using SQLAlchemy constructs so `downgrade()` is exact and tested.
- `emctl migrate` runs `alembic upgrade head` programmatically against
  `DATABASE_URL`; `env.py` reads the URL from the environment in both offline
  and online modes (no URL in `alembic.ini`). The migration directory ships
  inside the package, so `migrate` works from a checkout or an installed wheel.
- The `db/schema.sql` init-mount was removed from `docker-compose.yml` (it
  would double-create tables and collide with Alembic). Local bring-up is
  `docker compose up -d db` then `emctl migrate`.
- `db/schema.sql` is kept as the v1 **reference** with a header pointing at
  `emctl/migrations/`. Change the schema by adding a migration, then update the
  reference to match.

## Observability surface (schema v2, migration `0003`)

`0003` is additive and reversible (PRD `docs/prd/observability.md`). It adds two
tables — `risks` (EM-curated register, FKs to projects/decisions/prs) and
`task_events` (task status history, FK to tasks) — and three columns
(`decisions.status`/`significance`/`superseded_by`, `prs.task_id`). New columns
are nullable or carry `NOT NULL DEFAULT` values, so existing rows validate
without a data migration; `downgrade()` drops the additions in FK-safe order and
is round-trip tested (`tests/test_migrate.py`).

- **Generic backfill only.** `0003` seeds one synthetic `task_events` row per
  pre-existing task (`to_status` = current status, `actor='backfill'`) so
  cycle-time queries have a terminal event to anchor on. It hard-codes no ids
  and is a no-op on a fresh database. Platform-specific backfill (linking a
  specific PR to a task, seeding named risks) is an EM post-merge pass, not the
  migration's job.
- **`emctl_report_ro` reads the new tables** through `0002`'s
  `ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES`: the v2 tables are
  created by the same migrating role, so the default grant covers them. A test
  drives `metric report` (which `SET LOCAL ROLE emctl_report_ro`) against
  `risks`/`task_events` to prove it.

New commands follow the existing three-layer pattern (`commands/` → `repo/` →
`db`), parameterized SQL only, global `--json`, same exit-code contract:
`risk add|update|list|show`; `decision supersede` and `decision add`/`list`
gaining `--significance`/`--status`; `pr open|update --task`; and `task
create`/`update` writing a `task_events` row on status change (with an optional
`--by <role>` actor), read back by `task history <id>`. `risk update` and `risk
add` stamp `resolved_at` when `status` is anything other than `acknowledged`.

**Metrics remain data.** The three now-computable metrics (`cost_per_merged_pr`,
`cycle_time_days`, `rework_rate`) are registered by the EM post-merge via
`metric define`; they run on the unchanged `metric report` read-only boundary
(above). `tests/test_observability_metrics.py` proves each SQL runs and returns
rows through that path, but registers nothing.

## Token accounting by type (schema v2.1, migration `0004`)

`0004` is additive and reversible (PRD `docs/prd/token-accounting.md`). It adds
four nullable `BIGINT` columns to `runs` — `input_tokens`, `output_tokens`,
`cache_read_tokens`, `cache_write_tokens` — so per-run API token usage is
recorded **by type** rather than as the single `token_cost` lump (which is
≈ output tokens only). Measured cost is cache-dominated, so the lump under-counts
badly; the typed columns supersede it for cost projection. `token_cost` is left
untouched (legacy); `downgrade()` drops the four columns and is round-trip tested
(`tests/test_migrate.py`). All columns default NULL, so existing rows and runs
without a transcript validate without a data migration.

- **emctl surface** (same `commands/` → `repo/` → `db` pattern, parameterized
  SQL, global `--json`, unchanged exit-code contract): `run finish` gains
  optional `--input-tokens --output-tokens --cache-read --cache-write`; a **new
  `run update <RUN_ID>`** amends an already-finished run (correction /
  historical backfill) with those four flags plus `--tokens --cost --outcome
  --log-ref`. Unknown `RUN_ID` → `NotFoundError` (exit 3); a bad enum/value →
  `ValidationError` (exit 2). Only supplied flags are written, so an omitted
  flag never nulls a stored value; `run update` does not touch `ended_at` (it is
  not a finish).
- **Transcript aggregator (out of emctl, deliberately).**
  `tools/agent_token_split.py <transcript.jsonl>` sums the four token types from
  a Claude Code agent transcript (`message.usage`) and surfaces `message.model`,
  printing them as JSON. It is a pure read: one file opened read-only, tolerant
  of malformed / `usage`-less lines (never raises on a bad transcript), writing
  and executing nothing. Keeping it standalone isolates the Claude-Code
  transcript coupling to one file — emctl stays format-agnostic and takes the
  numbers via flags. The EM pipes its output into `run finish`/`run update`.
- **Metric is out of scope here.** The EM reprices `hypothetical_api_cost` from
  the typed columns post-merge via `metric define`, on the unchanged `metric
  report` read-only boundary; this task registers no metric.

## Testing

pytest against real Postgres (no mock DB). `conftest.py` points the app at
`DATABASE_URL_TEST`, runs the migrations once per session, and resets table
state between tests. Cover happy and unhappy paths: bad enums, missing files,
constraint violations, unset config, the READ ONLY boundary, and `--json`
stability — not just the demo case. CI wiring (a Postgres service in Actions)
is a phase-2 follow-up for implementer-devops.
