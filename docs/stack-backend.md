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
data, but it is treated as fallible and constrained by **four layers**, in
order of importance:

1. **Least-privilege role (the boundary).** Migration `0002` provisions a
   NOLOGIN role `emctl_report_ro` with `USAGE` on the schema and `SELECT` on all
   app tables (plus `ALTER DEFAULT PRIVILEGES ... GRANT SELECT` so future tables
   are covered) and **no** write/DDL privilege. The report path issues
   `SET LOCAL ROLE emctl_report_ro` before executing the definition, so the
   definition runs with no ability to write. NOLOGIN + `SET ROLE` is used
   deliberately: no new DSN, credential, or secret.
2. **Single statement.** The definition runs as a prepared statement
   (`conn.execute(definition, prepare=True)` → the extended query protocol),
   whose Parse phase rejects `;`-separated multi-statement input. This is
   load-bearing, not cosmetic: a `COMMIT` inside a multi-statement definition
   would end the transaction and discard `SET LOCAL ROLE`, reverting to the
   privileged session role — the exact `COMMIT; BEGIN READ WRITE; INSERT …;`
   escape a security review found. Blocking multi-statement is what keeps the
   role boundary intact. (Passing an empty params sequence does **not** force
   the extended protocol in psycopg 3; `prepare=True` does.)
3. **READ ONLY transaction.** `transaction(read_only=True)` (`emctl/db.py`) is a
   second guard against single-statement writes.
4. **Define-time validation.** `metric define`/`update` reject a definition that
   is not a single `SELECT`/`WITH` statement — fast-fail UX with a clear message,
   explicitly **not** the boundary (a read-only CTE is allowed at define time; a
   CTE that writes is stopped at report time by the role).

Tests seed hostile definitions directly into the table (bypassing define-time
validation) and assert the report path rejects the reviewer's exact PoC, a
CTE-write, and direct `INSERT`/`DELETE`/`TRUNCATE`/`DROP` — each with **zero**
state change — and that `emctl_report_ro` exists after `migrate` and cannot
write even in a writable transaction. The role is cluster-global; grants are
per-database and are (re)applied wherever `emctl migrate` runs. `0002`'s
downgrade revokes this database's grants but does not drop the role (a
cluster object other databases may depend on).

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

## Testing

pytest against real Postgres (no mock DB). `conftest.py` points the app at
`DATABASE_URL_TEST`, runs the migrations once per session, and resets table
state between tests. Cover happy and unhappy paths: bad enums, missing files,
constraint violations, unset config, the READ ONLY boundary, and `--json`
stability — not just the demo case. CI wiring (a Postgres service in Actions)
is a phase-2 follow-up for implementer-devops.
