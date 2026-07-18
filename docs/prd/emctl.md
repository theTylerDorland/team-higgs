# PRD — emctl (platform state CLI)

**Status:** proposed · **Owner:** EM (Higgs) · **Author tier:** plan
**Upstream authority:** `.claude/agents/em.md` → *emctl interface (contract)*.
That contract is the source of truth for the command surface; this PRD
designs how it is built. Where this PRD and the charter contract disagree,
the charter wins and this PRD is amended.

---

## 1. Purpose

`emctl` is the only interface any agent uses to read and write platform
state. State lives in Postgres; context windows are scratch. Without emctl
the charter's core discipline ("the DB is truth, write state before work
proceeds") is unenforceable — agents note *intended* state writes in prose
instead of executing them. This PRD covers the v1 build that makes every
state-touching rule in the charters literal.

## 2. Scope

**In (v1):** the full command contract — `status`, `migrate`, and CRUD over
`project`, `task`, `run`, `pr`, `review`, `artifact`, `question`,
`decision`, `metric`, `learning`, `debt`, `retro`. Alembic migrations
materializing schema v1. Tests. `docs/stack-backend.md` written from the
decisions below.

**Out (deliberate, tracked as follow-ups):**
- **CI wiring.** Tests need a Postgres service in Actions; workflows don't
  exist yet and are out of an implementer's remit. Follow-up task for
  implementer-devops in phase 2.
- **`emctl --version`.** Reserved as BOOTSTRAP phase-2's trivial
  end-to-end canary. Ship `__version__` in the package; do **not** add the
  CLI flag.
- **Cloud SQL.** v1 targets local Postgres 16 via `DATABASE_URL`. The
  migration to Cloud SQL is BOOTSTRAP phase 3.

## 3. Stack (sets `docs/stack-backend.md`)

- **Python 3.12+**, packaged with a single `pyproject.toml` at repo root;
  console-script entry point `emctl`; also runnable as `python -m emctl`.
- **Typer** for the CLI — typed subcommands matching the contract's shape,
  clean `--help`, easy `--json`.
- **psycopg 3** as the driver. Every query parameterized (`%s`/named
  params). No SQL assembled by string concatenation or f-strings —
  anywhere, including tests. This is also a security-blocker definition.
- **Alembic** for migrations (see §7).
- **ruff** (lint) + **mypy** (type check, no bare `dict`/`Any` on the
  public seams) + **pytest** (tests). All three must pass clean.
- New dependencies beyond these require justification in the PR.

## 4. Architecture

Three thin layers keep 12 command groups a *pattern*, not 12 bespoke
builds:

```
pyproject.toml              # deps, entry point, ruff/mypy/pytest config
alembic.ini
emctl/
  __init__.py               # __version__ (no CLI --version flag in v1)
  __main__.py               # python -m emctl -> cli.app()
  cli.py                    # root Typer app; mounts each command group; global --json
  config.py                 # settings from env: DATABASE_URL (required), DATABASE_URL_TEST
  db.py                     # psycopg3 connect; transaction() context manager; dict rows
  output.py                 # human table renderer + emit_json(); ISO-8601 timestamps
  errors.py                 # typed exceptions -> exit codes; DB-error mapping
  repo/                     # data layer, one module per table; parameterized SQL only
    projects.py tasks.py runs.py prs.py reviews.py questions.py
    decisions.py artifacts.py learnings.py debt.py metrics.py retros.py
    status.py               # cross-table summary queries
  commands/                 # Typer sub-apps, one per group; thin: parse -> repo -> render
    project.py task.py run.py pr.py review.py artifact.py question.py
    decision.py metric.py learning.py debt.py retro.py status.py migrate.py
  migrations/
    env.py                  # reads DATABASE_URL; offline + online modes
    versions/0001_initial_v1_schema.py
tests/
  conftest.py               # session: alembic upgrade on test DB; per-test tx rollback
  test_migrate.py test_status.py test_output.py test_errors.py
  test_projects.py ... (one per domain)
```

**Layer contracts.**
- `commands/*` never touch SQL; they validate input, call `repo`, and hand
  results to `output`. Enum flags are validated here (Typer `Enum`) against
  the schema's CHECK values, so bad `--status`/`--verdict`/`--outcome`/etc.
  is rejected with the valid list *before* a DB round-trip.
- `repo/*` never print and never read env; they take a connection and typed
  args, return plain dicts/lists. One transaction per command invocation.
- `db.py` owns connection + transaction lifecycle; `output.py` owns all
  rendering; `errors.py` owns exit-code mapping. A command file should be
  readable top-to-bottom without opening the others.

## 5. Command contract → schema mapping

Build exactly the charter surface. Flags that differ from column names, and
the non-obvious semantics, are pinned here; anything unspecified follows the
column name and type in `db/schema.sql`.

| Command | Notes / flag→column |
|---|---|
| `status` | Global summary: active projects; task counts by status; `awaiting_tyler` queue; open questions (blocking first); open PRs; notable recent `runs` token costs. Read-only. |
| `migrate` | `alembic upgrade head` (see §7). No args in v1. |
| `project create\|show\|list` | `--name --repo --brief`; `--status` (active\|paused\|done\|archived). `show` by id or name. |
| `task create\|update\|show\|list` | `--title --spec --project --role`; `--tier`→`model_tier` (plan\|execute\|local); `--prd-ref`→`prd_ref`; `--status`; `--branch`; `--depends-on` (repeatable int → `depends_on int[]`); `--blocked-reason`→sets `blocked=true`+`blocked_reason`, `--unblock` clears both. `list` filters: `--status --project --role --blocked`. |
| `run start\|finish` | `start --task --role --model --mode` (team\|subagent\|headless\|interactive) inserts and prints the run id. `finish` identifies the run by `--run <id>`, or by `--task <id>` (finishes that task's latest still-open run — matches the `run finish --task` example in the implementer charters); sets `--outcome` (done\|negative-result\|blocked\|failed) `--tokens`→`token_cost` `--cost`→`cost_usd` `--log-ref`→`log_ref` and `ended_at=now()`. |
| `pr open\|update\|show` | `--project --github-pr`; `--risk`→`risk_level` (low\|medium\|high); `--summary-file`→reads file into `em_summary`; `--status` (open\|merged\|rejected\|closed); `--decision`→`tyler_decision` (+ sets `decided_at`). |
| `review add` | `--pr --role --model --verdict` (approve\|concerns\|block) `--findings-file`→JSON file parsed into `findings` JSONB `--objection`→`strongest_objection`. |
| `artifact create\|decide\|list` | `--project --task --type` (mockup\|diagram\|spec\|schema\|model\|eval-set\|prompt) `--path`. `decide --artifact <id> --status` (approved\|rejected\|superseded) `--notes` (+ sets `decided_at`). |
| `question add\|answer\|list` | `--project --body --blocking`. `answer --question <id> --answer` (+ `answered_at`). `list --blocking` filters open blockers. |
| `decision add\|list` | `--project --title --context --decision`. |
| `metric define\|update\|list\|report` | `--name` `--query`→`definition` `--rationale` `--status` (proposed\|active\|retired). `report --name` runs the stored `definition` **in a READ ONLY transaction** and renders rows (see §6, §8). |
| `learning add\|list\|resolve` | `--category` (start\|stop\|keep\|question) `--observation`→`observation` `--evidence`; `filed_by` from `--role`. `resolve --learning <id> --retro`→sets `status=resolved`, `retro_id`. `list --category --status`. |
| `debt add\|list\|resolve\|merge` | `--where`→`location` (required) `--kind` (duplication\|coupling\|missing-tests\|pattern-drift\|dead-code\|docs\|other) `--severity` (high\|medium\|low) `--evidence` (required); `filed_by` from `--role`. `resolve --debt <id> --resolved-ref`. `merge --into <keeper_id> <dup_id>...`→each dup `status=resolved` with a pointer, keeper `recurrence += count`. |
| `retro open\|close\|list` | `--trigger --doc-path`. `close --retro <id>`→`closed_at`. |

**ID vs. slug.** `show`/`update`/`decide`/`answer`/`resolve`/`finish` accept
the integer id; `project show` additionally accepts the unique name. Unknown
id → `NotFoundError` (exit 3), never a silent no-op.

## 6. Cross-cutting design

- **Output.** Human-readable tables by default; a global `--json` on the
  root app switches every command to deterministic JSON on stdout (nothing
  else on stdout). Agents parse `--json`. Timestamps ISO-8601 UTC.
- **Config.** `DATABASE_URL` (required; unset → `ConfigError`, exit 5),
  `DATABASE_URL_TEST` (tests only). No connection literals anywhere.
- **Errors & exit codes.** `EmctlError` base with: `ConfigError`=5,
  `ValidationError`=2 (bad flag/enum/missing file), `NotFoundError`=3,
  `ConflictError`=4 (unique/FK violation, e.g. duplicate project name or
  `(project, github_pr)`), generic=1. psycopg `IntegrityError` /
  `CheckViolation` are caught in `repo`/`errors` and mapped to these — raw
  SQL, tracebacks, and connection strings never reach stdout/stderr.
- **`metric report` trust boundary.** The stored `definition` is
  operator-authored SQL (written via `metric define` by the EM), not
  external input. It still runs inside a `READ ONLY` transaction so a
  malformed or mistaken definition cannot mutate state. This is documented
  at the `report` command and in `stack-backend.md`, and is the pre-empted
  answer to the security review's inevitable question.

## 7. Migrations (Alembic — Tyler's call)

- `versions/0001_initial_v1_schema.py` faithfully reproduces
  `db/schema.sql`: all 12 tables, every CHECK constraint, defaults
  (including `depends_on '{}'`), the 5 partial/normal indexes, UNIQUE
  constraints, and FKs. `downgrade()` drops everything in FK-safe order and
  is exercised by tests.
- `emctl migrate` invokes Alembic programmatically
  (`command.upgrade(cfg, "head")`) with `DATABASE_URL`; `env.py` reads the
  URL from env in both offline and online modes (no URL in `alembic.ini`).
- **Reconciliation (EM decision, recorded as a `decisions` row).** Two
  schema sources drift, so **migrations become operative truth**:
  - Remove the `./db/schema.sql` init-mount from `docker-compose.yml` (it
    would double-create tables and collide with Alembic). Local bring-up
    becomes `docker compose up` → `emctl migrate`.
  - Keep `db/schema.sql` as the v1 **reference** with a header note pointing
    at `emctl/migrations/` as the operative source going forward.
  - A test asserts the migrated schema matches intent: all 12 tables + named
    indexes exist, and representative CHECK constraints reject invalid
    values.

## 8. Testing

- **pytest**, real Postgres (no mock DB). `conftest.py`: once per session,
  create/point at `DATABASE_URL_TEST` and `alembic upgrade head`; per test,
  open a transaction and roll it back at teardown for isolation.
- **Coverage — happy + unhappy, per the backend charter:**
  - each domain: create → list → show → update happy path;
  - `NotFoundError` on unknown id; `ConflictError` on duplicate unique
    (project name, `(project, github_pr)`); `ValidationError` on bad enum
    and on missing `--summary-file`/`--findings-file`; `ConfigError` on
    unset `DATABASE_URL`;
  - `task` `depends_on` array round-trips (repeatable flag → `int[]`);
    `--blocked-reason`/`--unblock` toggles;
  - `run start`→`finish` sets `ended_at`, `outcome`, costs;
  - `pr` `--summary-file` and `review` `--findings-file` ingest file
    contents; malformed `findings` JSON → `ValidationError`;
  - `metric report` runs a stored query and **rejects a mutating
    definition** (READ ONLY enforced);
  - `debt merge` bumps `recurrence` and resolves dups with a pointer;
  - `status` aggregates correctly on seeded data;
  - `--json` output parses and is stable; error paths emit clean messages
    and the right exit codes.

## 9. Definition of done

Verified by running, not asserting:
- `ruff` + `mypy` clean; full `pytest` green against a fresh DB; downgrade
  then upgrade round-trips.
- `emctl migrate` on an empty DB creates schema v1; a manual round-trip
  (`project create` → `task create` → `run start/finish` → `pr open` →
  `review add` → `status`) works in both table and `--json` modes.
- `docs/stack-backend.md` exists and captures §3, §6 (`metric report`
  boundary), and §7 (migrations-as-truth).
- PR description follows the backend implementer contract, declaring every
  deviation and known gap.

## 10. Dispatch metadata

- **Task:** "Build emctl (platform state CLI), full contract" — BOOTSTRAP
  task 1.
- **Role:** implementer-backend · **Tier:** execute · **prd_ref:**
  `docs/prd/emctl.md` · **depends_on:** none · **branch:**
  `feat/emctl` (implementer works only on this branch).
- **Reviewers:** security always; QA when instantiated. Reviewer runs on a
  different model than the author where the dispatch layer allows.

## 11. Intended state writes (emctl not yet live)

Per BOOTSTRAP, until emctl exists these are noted, not executed; the EM
backfills them immediately after merge:
- `projects` row: **team-higgs / platform** (repo `team-higgs`).
- `tasks` row: this task, `role=implementer-backend`, `tier=execute`,
  `prd_ref=docs/prd/emctl.md`, status tracked through the vocabulary.
- `runs` rows: the implementer run and each reviewer run.
- `decisions` rows: (a) migrations-as-operative-truth over `db/schema.sql`;
  (b) `metric report` runs in a READ ONLY transaction;
  (c) `--version` deferred as the phase-2 canary.
- `prs` + `reviews` rows once the PR opens and reviews land.
