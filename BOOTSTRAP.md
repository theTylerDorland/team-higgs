# Bootstrap

Ordered. Phases 0–2 run entirely local + GitHub — GCP (phase 3) is
deliberately deferred until there is something to deploy, so the first
loop has minimum activation energy.

## Phase 0 — Repo (you, ~30 min)

1. Create the private GitHub repo; push this scaffold as the initial
   commit.
2. Branch protection on `main`: require a PR, require your review,
   dismiss stale approvals, no force pushes, no deletions. This is the
   enforcement behind "only Tyler merges" — do it before any agent works.
3. Security features on: Dependabot alerts + updates, secret scanning
   with push protection.
4. Verify `.claude/settings.json` deny patterns against current Claude
   Code docs (syntax drifts; the intent is documented inline).

## Phase 1 — First loop, local (you + the team, first sessions)

5. Local Postgres: `docker compose up` (compose file is part of task 1 —
   until then, any local Postgres 16 works). Apply `db/schema.sql`.
6. Open Claude Code in the repo. First conversation with the EM:
   introduce yourself briefly, then dispatch **task 1: build emctl** per
   the contract at the end of the charter — Python CLI, Postgres, typed
   subcommands, `migrate` command that applies `db/schema.sql`.
   Implementer-backend builds it on a branch and opens the PR.
7. Dispatch the security review of that PR (interactively for now — the
   Action doesn't exist yet). Read the findings file and the EM's
   synthesized report. Merge if it earns it. **This is the whole system
   in miniature: judge everything about the experience, not just the
   code.**
8. With emctl live: EM backfills project/task/run/PR/review rows for
   what just happened, and every rule in the charters becomes literal.

## Phase 2 — Automation (supervised)

9. Author the bootstrap workflows with Claude Code interactively (you
   are the control plane's first author, deliberately):
   - `review.yml` — PR opened → headless reviewer runs → EM synthesis →
     report as PR comment.
   - `on-merge.yml` — merge → tech-writer publish pass → emctl updates.
   Pin actions by SHA; least-privilege permissions blocks.
10. Run one trivial end-to-end task ("add `emctl --version`") without
    touching anything yourself: intake → task row → branch → PR →
    automated review → report → your merge → docs pass. Fix what the
    run exposes; iterate until the loop is boring.
11. First retro-ish moment: ask the EM for a status digest and read it
    critically. Tune report formats now, while changing them is cheap.

## Phase 3 — GCP (when something needs to deploy)

12. Day zero per `docs/stack-devops.md` — supervised session, once.
13. Task: Terraform base stack (state bucket config, Cloud SQL, Artifact
    Registry, Cloud Run service, WIF) via implementer-devops. Plan in
    the PR; apply on your merge.
14. Migrate emctl's target DB from local to Cloud SQL; add the
    `apply-on-merge` workflow through the devops governed exception.

## Phase 4 — Scale out (no schedule; triggered by need)

- Agent Teams for multi-layer features (experimental flag; verify
  current docs).
- Remaining reviewer instantiations (QA, backend, frontend, data) — EM
  drafts, you review. Include the maintainability item and the ML
  eval-gate item.
- Repo template for product repos; EM gains repo-creation-with-approval.
- Agent SDK service + web UI (kanban over tasks, awaiting_tyler queue,
  chat to EM). Verify SDK auth/billing model against docs first.
- Production alert → EM intake; multi-model review panel; local model
  routing; `docs/stack-ml.md`.
