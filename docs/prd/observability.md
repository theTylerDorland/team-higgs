# PRD — Project observability (schema v2: risks, decisions, metrics)

**Status:** proposed · **Owner:** EM (Higgs) · **Author tier:** plan
**Upstream authority:** `.claude/agents/em.md`. This PRD adds a state surface
the charter implies but v1 can't express; where it and the charter disagree,
the charter wins and this PRD is amended.

---

## 1. Purpose

When we look over a project we want to answer three questions the current
schema can't:

1. **What risks were acknowledged, and are they mitigated, accepted, or
   realized?** Today risks scatter across PR `Risk:` fields, reviewer
   findings, known-gaps, and debt — there is no register.
2. **What were the high-level decisions, and are any superseded?** The
   `decisions` table is flat: no status, no supersession link, no way to
   separate headline decisions from routine ones. (Concretely: this loop
   couldn't mark the `metric report` decision *superseded* — it was recorded
   in prose.)
3. **What did the work cost and how long did it take?** Three of the five
   charter-core metrics — **cost per merged PR**, **cycle time**, **rework
   rate** — are not computable from v1: `prs` has no link to the `task`/`runs`
   that produced it, and `tasks` keeps only current status, no history.

These are one problem: the data model for a future **project dashboard**
(risk register + decision log + analytics). This PRD is schema v2 plus the
`emctl` surface to populate it. The UI itself is out of scope.

## 2. Scope

**In:**
- New `risks` table (EM-curated register, linked to decisions/PRs).
- `decisions` upgrade: `status`, `significance`, `superseded_by`.
- `prs.task_id` link + a `task_events` status-history table.
- `emctl` surface: `risk` command group; `decision` supersede/significance;
  `task` status changes writing `task_events`; `pr --task`.
- Register the three now-computable metrics; keep the four existing.
- Alembic migration `0003`, additive and reversible; tests; backfill of
  existing rows (PR #5 ↔ task #1); `docs/stack-backend.md` + charter contract
  updated for the new commands.

**Out (deliberate):**
- **The UI.** This PRD makes the data queryable; the dashboard is later work
  designed against this schema.
- **Auto-derived risks.** Decision: EM-curated with links (a risk is filed
  deliberately, like a decision or debt item, not scraped from findings).
- **Retro/analytics automation** beyond defining the metrics.

## 3. Schema changes (migration `0003`, additive)

**New `risks` table.**
```
id            SERIAL PK
project_id    INT NOT NULL REFERENCES projects(id)
title         TEXT NOT NULL
body          TEXT                       -- description / context
category      TEXT NOT NULL CHECK IN ('security','architecture','operational',
                                      'cost','dependency','product')
severity      TEXT NOT NULL CHECK IN ('high','medium','low')
status        TEXT NOT NULL DEFAULT 'acknowledged'
              CHECK IN ('acknowledged','mitigated','accepted','realized','closed')
mitigation    TEXT                       -- how addressed, or why accepted
decision_id   INT REFERENCES decisions(id)   -- decision that accepted/mitigated it
pr_id         INT REFERENCES prs(id)         -- where it surfaced (optional)
acknowledged_by TEXT                     -- role
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
resolved_at   TIMESTAMPTZ               -- set when status leaves 'acknowledged'
```
`status` semantics: **acknowledged** (known, unaddressed) → **mitigated**
(action reduced it) | **accepted** (we live with it, `mitigation` says why) |
**realized** (it happened) | **closed** (no longer relevant). *Risk is not
debt:* debt is code you intend to fix (codebase-health lane); a risk may be
accepted forever. They cross-link freely — one item can be both a `debt` row
and an `accepted` risk.

**`decisions` upgrade (ALTER).**
```
ADD status        TEXT NOT NULL DEFAULT 'accepted'
                  CHECK IN ('proposed','accepted','superseded','reversed')
ADD significance  TEXT NOT NULL DEFAULT 'major'
                  CHECK IN ('major','minor')   -- 'minor' = routine/operational
ADD superseded_by INT REFERENCES decisions(id)
```
Default `significance='major'`: `decisions` rows already mean "architectural
consequence" per the charter, so they are high-level by default; tag routine
ones `minor`. (Open for your review — flip the default if you'd rather opt in
to "major".) The project view shows `status='accepted' AND significance='major'`.

**`prs.task_id` (ALTER).**
```
ADD task_id INT REFERENCES tasks(id)    -- the task this PR implements (nullable:
                                         -- docs/infra PRs may have none)
```
Unlocks per-PR cost by joining `prs → tasks → runs`.

**New `task_events` table (status history).**
```
id          SERIAL PK
task_id     INT NOT NULL REFERENCES tasks(id)
from_status TEXT                        -- null on creation
to_status   TEXT NOT NULL
actor       TEXT                        -- role that made the change
at          TIMESTAMPTZ NOT NULL DEFAULT now()
INDEX (task_id)
```
Written by `emctl` on every status change (see §4). Unlocks cycle time
(first→`done`) and rework (re-entry into `in_progress`/`in_review` after a
prior `in_review`).

**Indexes:** `idx_risks_open ON risks(status) WHERE status='acknowledged'`;
`idx_task_events_task ON task_events(task_id)`.

## 4. emctl surface additions

Follows v1's three-layer pattern (`commands/` → `repo/` → `db`), parameterized
SQL only, global `--json`, same exit-code contract.

| Command | Notes |
|---|---|
| `risk add` | `--project --title --body --category --severity --status --mitigation --decision <id> --pr <id> --by`. Defaults `status=acknowledged`. |
| `risk update <RISK_ID>` | `--status --severity --mitigation --decision`. Setting `status` off `acknowledged` sets `resolved_at`. |
| `risk list` | filters `--project --status --category --severity`. |
| `risk show <RISK_ID>` | full row + linked decision/PR. |
| `decision add` | **+** `--significance` (major\|minor, default major), `--status`. |
| `decision supersede <OLD_ID> --by <NEW_ID>` | sets OLD `status=superseded`, `superseded_by=NEW`. |
| `decision list` | **+** `--significance --status` filters; output shows status. |
| `task create` / `task update` | on create and on every `--status` change, write a `task_events` row (`from`/`to`/`actor`/`at`); add optional `--by <role>` for the actor. Behaviour otherwise unchanged. |
| `task history <TASK_ID>` | list `task_events` for a task (chronological). |
| `pr open` / `pr update` | **+** `--task <id>` to link the PR to its task. |

**Metrics (EM registers post-migration; listed here as deliverables).** Keep
the four already defined; add:
- `cost_per_merged_pr` — `SELECT p.github_pr, coalesce(sum(r.token_cost),0) FROM prs p JOIN runs r ON r.task_id = p.task_id WHERE p.status='merged' GROUP BY p.github_pr`.
- `cycle_time_days` — per task, `done` event time minus first `planned` event time from `task_events`.
- `rework_rate` — share of tasks with a `task_events` re-entry into `in_progress`/`in_review` after a prior `in_review` (complements `review_rounds_per_pr`).

These must run under the existing `metric report` read-only boundary (§6 of
the emctl PRD) — no exception.

## 5. Migration & backfill discipline

- `0003` is purely additive (new tables + nullable columns with safe
  defaults); existing rows validate. `downgrade()` drops the new tables and
  columns in FK-safe order and is tested.
- **Backfill (by the migration where deterministic, else a one-off EM pass):**
  existing `decisions` get `status='accepted'`, `significance='major'`;
  `prs.task_id` for PR #5 → task #1; `risks` seeded from this loop's
  acknowledged risks (the accepted `SET LOCAL ROLE` weakness, the compose
  dev-password, the two EM spec-misses) linked to their decisions.
- **Known gap:** task #1 predates history, so it has no real `task_events`
  trail; the migration seeds a single synthetic `→done` event (marked
  `actor='backfill'`) so cycle-time queries don't null-out. Declared, not
  hidden.

## 6. Definition of done

- `ruff` + `mypy` clean; full `pytest` green on a fresh DB; `0003`
  downgrade→upgrade round-trips.
- New commands exercised happy + unhappy (bad enum, missing FK, not-found,
  `risk update` sets `resolved_at`, `decision supersede` sets both sides,
  `task update` writes a correct `task_events` row, `pr --task` links).
- The three new metrics registered and each returns rows via `metric report`
  (read-only boundary intact).
- `db/schema.sql` reference updated; `docs/stack-backend.md` extended; the
  charter's *emctl interface (contract)* gains the new commands (companion
  charter PR — see §8).

## 7. Dispatch metadata

- **Role:** implementer-backend · **Tier:** execute · **prd_ref:**
  `docs/prd/observability.md` · **depends_on:** none (emctl v1 merged) ·
  **branch:** `feat/observability`.
- **Reviewers:** security always (new SQL surface + `metric` definitions);
  cross-model vs. the author.

## 8. Companion charter amendment (separate PR)

The `emctl` contract in `.claude/agents/em.md` must gain the `risk` group and
the `decision supersede` / `--significance` and `pr --task` flags, and the
*Continuous improvement* section should name the **risk register** as an
EM-owned ledger alongside debt, learnings, and metrics (EM-curated; a risk is
filed when acknowledged and linked to the decision that dispositions it). This
ships as its own charter PR so the contract and the build land together.
