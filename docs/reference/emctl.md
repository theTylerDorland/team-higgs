# `emctl` command reference

`emctl` is the command-line tool for reading and writing all platform
state. Every command reads from or writes to the platform database, prints
a result, and exits with a code you can check in a script.

Run it as `emctl <command>` or, equivalently, `python -m emctl <command>`.
Run `emctl` with no arguments, or add `--help` to any command, to see its
options.

## Before you start

`emctl` needs to know which database to talk to. Set the `DATABASE_URL`
environment variable to your database connection string before running any
command. If it is not set, the command stops immediately and exits with
code 5.

To create the tables in a fresh database, run `emctl migrate` once (see
[migrate](#migrate)).

## Output and the `--json` flag

By default every command prints a readable table. Add `--json` to get the
same result as machine-readable JSON on standard output, with nothing else
mixed in — useful when another program reads the result. Place it before
the command:

```
emctl --json task list --status planned
```

Timestamps are always shown in UTC.

## How options are shown here

- Required options are marked **(required)**.
- Where an option accepts a fixed set of values, the choices are listed;
  anything else is rejected before the database is touched (exit code 2).
- Some commands take an id or name directly after the subcommand — shown
  below as `<id>` — rather than as a `--flag`.

---

## `status`

Prints a global summary: active projects, task counts by status, the
awaiting-Tyler queue, open questions (blocking ones first), open PRs, and
recent run costs. Read-only; takes no options.

```
emctl status
```

## `migrate`

Sets up the database by applying all pending schema updates. Run it once on
a new database, and again after any update that adds to the schema. Takes
no options.

```
emctl migrate
```

## `project`

- **`project create`** — `--name` **(required)**, `--repo` **(required)**,
  `--brief`, `--status` (`active`, `paused`, `done`, `archived`).
- **`project show <id-or-name>`** — look up one project by its id or its
  unique name.
- **`project list`** — `--status` to filter.

## `task`

- **`task create`** — `--title` **(required)**, `--project` **(required,
  project id)**, `--spec`, `--role`, `--tier` (`plan`, `execute`,
  `local`), `--prd-ref`, `--status`, `--branch`, `--depends-on` (a task id;
  repeat the option for several), `--by` (the role making the change,
  recorded in the task's history).
- **`task update <id>`** — `--status`, `--role`, `--tier`, `--prd-ref`,
  `--branch`, `--depends-on` (repeatable), `--blocked-reason` (marks the
  task blocked and records why), `--unblock` (clears the block), `--by`
  (the role making the change, recorded in the task's history).
  `--blocked-reason` and `--unblock` cannot be used together.
- **`task history <id>`** — list the task's status changes in order, each
  showing the status it moved from and to, the role that made the change,
  and when.
- **`task show <id>`**.
- **`task list`** — filter with `--status`, `--project`, `--role`,
  `--blocked`.

Task status values: `backlog`, `planned`, `in_progress`, `in_review`,
`awaiting_tyler`, `done`.

Each status change is recorded in the task's history; `--by` notes which
role made it. See **`task history`** to read the timeline back.

## `run`

- **`run start`** — `--role` **(required)**, `--model` **(required)**,
  `--mode` **(required)** (`team`, `subagent`, `headless`, `interactive`),
  `--task` (task id). Prints the new run's id.
- **`run finish`** — identify the run with either `--run` (run id) or
  `--task` (finishes that task's latest still-open run); one of the two is
  required. `--outcome` **(required)** (`done`, `negative-result`,
  `blocked`, `failed`), `--tokens`, `--cost` (US dollars, e.g. `1.2500`),
  `--log-ref`.

## `pr`

- **`pr open`** — `--project` **(required, project id)**, `--github-pr`
  **(required)**, `--risk` (`low`, `medium`, `high`), `--summary-file` (a
  file whose contents become the summary), `--status` (`open`, `merged`,
  `rejected`, `closed`), `--task` (the id of the task this PR implements).
- **`pr update <id>`** — `--status`, `--risk`, `--summary-file`,
  `--decision`, `--task` (the id of the task this PR implements).
- **`pr show <id>`**.

## `review`

- **`review add`** — `--pr` **(required, PR id)**, `--role`
  **(required)**, `--verdict` **(required)** (`approve`, `concerns`,
  `block`), `--objection` **(required)** (the strongest objection),
  `--model`, `--findings-file` (a JSON file of detailed findings).

## `artifact`

- **`artifact create`** — `--project` **(required, project id)**, `--type`
  **(required)** (`mockup`, `diagram`, `spec`, `schema`, `model`,
  `eval-set`, `prompt`), `--path` **(required)**, `--task` (task id).
- **`artifact decide`** — `--artifact` **(required, artifact id)**,
  `--status` **(required)** (`approved`, `rejected`, `superseded`),
  `--notes`.
- **`artifact list`** — filter with `--project`, `--task`, `--type`.

## `question`

- **`question add`** — `--body` **(required)**, `--project` (project id),
  `--blocking` (mark it as blocking).
- **`question answer`** — `--question` **(required, question id)**,
  `--answer` **(required)**.
- **`question list`** — `--blocking` shows only open blocking questions.

## `decision`

- **`decision add`** — `--title` **(required)**, `--decision`
  **(required)**, `--project` (project id), `--context`, `--significance`
  (`major`, `minor`; default `major`), `--status` (`proposed`, `accepted`,
  `superseded`, `reversed`).
- **`decision supersede <old-id>`** — `--by` **(required, the id of the
  decision that replaces it)**. Marks the old decision superseded and
  records which decision replaced it.
- **`decision list`** — filter with `--project`, `--significance`,
  `--status`.

Decision status values: `proposed`, `accepted`, `superseded`, `reversed`.
Significance is `major` or `minor` — mark routine choices `minor` to keep
them separate from the headline decisions.

## `metric`

- **`metric define`** — `--name` **(required)**, `--query` **(required)**
  (the SQL that produces the metric), `--rationale` **(required)**,
  `--status` (`proposed`, `active`, `retired`).
- **`metric update`** — `--name` **(required)**, `--query`, `--rationale`,
  `--status`.
- **`metric list`** — `--status` to filter.
- **`metric report`** — `--name` **(required)**. Runs the stored metric and
  prints its rows. This command is read-only: it cannot change any data,
  so a metric definition that tries to write is refused.

## `learning`

- **`learning add`** — `--category` **(required)** (`start`, `stop`,
  `keep`, `question`), `--observation` **(required)**, `--evidence`,
  `--role` (records who filed it).
- **`learning resolve`** — `--learning` **(required, learning id)**,
  `--retro` **(required, retro id)**.
- **`learning list`** — filter with `--category`, `--status` (`open`,
  `resolved`, `escalated`).

## `debt`

- **`debt add`** — `--where` **(required)** (the location), `--kind`
  **(required)** (`duplication`, `coupling`, `missing-tests`,
  `pattern-drift`, `dead-code`, `docs`, `other`), `--severity`
  **(required)** (`high`, `medium`, `low`), `--evidence` **(required)**,
  `--project` (project id), `--role` (records who filed it).
- **`debt resolve`** — `--debt` **(required, debt id)**, `--resolved-ref`
  **(required)**.
- **`debt merge`** — `--into` **(required, the debt id to keep)**, followed
  by one or more duplicate debt ids. The duplicates are resolved and point
  to the kept item, whose recurrence count goes up.
- **`debt list`** — filter with `--status` (`open`, `proposed`,
  `resolved`, `stale`, `escalated`), `--severity`, `--kind`.

## `risk`

The risk register records risks on a project — what they are, how serious
they are, and how they were addressed.

- **`risk add`** — `--project` **(required, project id)**, `--title`
  **(required)**, `--category` **(required)** (`security`, `architecture`,
  `operational`, `cost`, `dependency`, `product`), `--severity`
  **(required)** (`high`, `medium`, `low`), `--body` (a description),
  `--status` (`acknowledged`, `mitigated`, `accepted`, `realized`,
  `closed`; default `acknowledged`), `--mitigation` (how it was addressed,
  or why it is accepted), `--decision` (the id of a related decision),
  `--pr` (the id of a related PR), `--by` (the role acknowledging it).
- **`risk update <id>`** — `--status`, `--severity`, `--mitigation`,
  `--decision` (the id of a related decision).
- **`risk list`** — filter with `--project`, `--status`, `--category`,
  `--severity`.
- **`risk show <id>`** — the full risk, with its linked decision and PR.

Risk status values: `acknowledged`, `mitigated`, `accepted`, `realized`,
`closed`.

## `retro`

- **`retro open`** — `--trigger` **(required)**, `--doc-path`.
- **`retro close`** — `--retro` **(required, retro id)**.
- **`retro list`**.

---

## Exit codes

Every command exits with one of these codes, so scripts can react to the
outcome:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic error |
| 2 | Invalid input (a bad option, value, or input file) |
| 3 | Not found (the id or name you referenced does not exist) |
| 4 | Conflict (a uniqueness or reference rule was violated, e.g. a duplicate project name) |
| 5 | Configuration error (`DATABASE_URL` is not set) |
