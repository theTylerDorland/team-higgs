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

`metric report` executes the stored `definition` of a metric. That definition
is operator-authored SQL, written by the EM via `metric define` — it is trusted
input, not external data. It is nonetheless run inside a **READ ONLY**
transaction (`emctl/db.py` `transaction(read_only=True)`), so a mistaken or
malformed definition can only ever read: an attempted write raises and is
mapped to an error, and state is unchanged. A test asserts a mutating
definition is rejected and writes nothing. This is the pre-empted answer to the
security review: the boundary is defence-in-depth around trusted-but-fallible
operator SQL, not a sandbox for untrusted input.

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
