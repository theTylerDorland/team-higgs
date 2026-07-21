# PRD — Command center (the emctl web frontend)

**Status:** proposed · **Owner:** EM (Higgs) · **Author tier:** plan
**Upstream authority:** `.claude/agents/em.md` (charter) and platform
decisions **#15–#20**. Where this PRD and the charter disagree, the charter
wins and this PRD is amended. The **approved mockup**
(`docs/design/command-center-v1.html`, extending the approved
`emctl-approval-mockup-v1.html`) is the build spec for the UI; where this PRD
and the approved mockup disagree on layout/interaction, the mockup wins.

---

## 1. Purpose

The command center is Tyler's **visual operating surface** over platform
state — the `emctl` state store given a browser face. Today Tyler drives the
team from a terminal 1:1 with Higgs. That stays the place work is *ideated and
launched*. The command center is where he **approves artifacts, grooms and
queues the backlog, reviews the team's own retrospective findings, keeps his
own notes, and watches state** — without a Claude Code session open.

It exists because the charter's core loop (an `awaiting_tyler` queue, plus
retros and continuous improvement) deserves a real surface, and because
approving a rendered artifact in-app is how Tyler already prefers to work
(the insight that produced this project).

## 2. Scope

**In (v1):**
- **Approval queue.** The `awaiting_tyler` queue: list items, render the
  attached artifact inline (mockups rendered, PR reports readable, PRD diffs),
  **approve / reject in place** (writes `tyler_decision`).
- **Backlog grooming.** Greenlight a task (mark ready-to-dispatch), reorder /
  prioritize, block / unblock — over the real status vocabulary
  (`backlog → planned → in_progress → in_review → awaiting_tyler → done`,
  `blocked` a flag).
- **Create task.** Author a new backlog item (title, spec, project, role,
  model tier).
- **Continuous-improvement space.** Review **retros, learnings, and debt**
  (already in emctl), and **schedule improvement activities** — where
  "schedule" is creating / greenlighting a task, not running anything.
- **Notes.** A space for Tyler's own thoughts — append-only text notes.
- **Read-only state.** PRs, risks, questions, and recent run costs — the rest
  of `emctl status` made visual.

**Out (deliberate, tracked as follow-ups):**
- **Running agents from the UI.** The deferred north star. The UI **never
  spawns compute** (decisions #15/#16); greenlighting is a state change that
  Higgs picks up and dispatches in-session, on the subscription. Revisit only
  when the cost story supports a subscription-tied runner.
- **Blob storage / file uploads.** Notes and findings are text in Postgres;
  versioned docs stay in git (decision #20). Add a GCS bucket only when a real
  binary/upload need appears.
- **Multi-user.** Auth is single-user (Tyler). No roles/teams surface.

## 3. Architecture

- **Colocated in `team-higgs`** (decision #18). The backend is
  **emctl-over-HTTP**: a FastAPI service that **reuses emctl's data layer**
  (`emctl/db.py`, the per-entity repos, the schema) rather than duplicating
  it. Factor the shared read/write logic into a module both the CLI and the
  API import; the API must not reimplement queries emctl already owns.
- **One image, one deploy** (`docs/stack-frontend.md`): FastAPI serves the
  built SPA alongside the JSON API.
- **SPA:** React + TypeScript + Vite + Tailwind, built to the approved mockup,
  consuming the backend's **OpenAPI contract** — no business logic the API
  already computes.

## 4. API surface (emctl-over-HTTP)

Read + write endpoints backing the surfaces in §2, over the existing schema:
approval queue + artifact fetch; approve/reject; task grooming (status
transitions, priority) + create; retros/learnings/debt (read) + create
improvement task; notes (append + list); read-only PRs / risks / questions /
run-costs. Every endpoint is **authenticated** (§6) and **none spawns compute
or invokes the API/agents** (decision #16). Typed request/response models;
OpenAPI published for the SPA build.

## 5. Schema change (additive, reversible)

One new **`note`** entity for Tyler's thoughts — append-only, consistent with
the platform's event-log model (id, body, created_at, and author/context as
the repo pattern dictates). New Alembic migration, additive only. No changes
to existing tables required for v1; grooming and approvals write through
existing columns (`status`, `tyler_decision`, priority/ordering as the task
repo supports — confirm during backend build, add a minimal additive column
only if ordering isn't already expressible).

## 6. Auth & deploy

- **Own gated Cloud Run service** on `higgs.tylerdorland.com` — **not** the
  `higgs-command` placeholder. Retiring the placeholder's `allUsers`
  `run.invoker` at cutover closes **platform risk #3** (decision #17).
- **Google OIDC-in-app**, reusing plant-log's proven path.
  `ALLOWED_EMAILS` = Tyler only. **Cloud Run ingress locked** so the service
  isn't openly invokable; secrets in Secret Manager; `DEV_AUTH` never set in
  prod.
- Terraform under `infra/`; pairs with the Terraform-in-CI task (#23) once it
  lands. Security reviews the service, the auth gate, and the ingress config.

## 7. Approval → merge flow & session notification

**Merges flow through the GitHub API directly from the command center — not
back through a Claude Code session** (decision #21). When Tyler approves a
PR-backed item, the service (a) records `tyler_decision` in Postgres and
(b) merges the PR via the GitHub API on his behalf. Tyler is the only
authorized merger (branch protection enforces this); requiring a live Higgs
session to merge would make him wait on compute he's keeping off the critical
path. Merging is an external state change, not an agent run, so it stays inside
the "writes state, never spawns compute" boundary (decision #16).

**Credential custody:** the service holds a **least-privilege GitHub token**
(merge on the two repos, nothing more) in Secret Manager; only Tyler's
authenticated, allowlisted session can trigger a merge; security reviews token
scope and custody. *Phaseable:* if we'd rather ship the DB-approval surface
first, v1 records the decision and Higgs merges in-session, with merge-from-UI
as the immediate fast-follow.

**Session notification — the DB is the message bus.** There is no free
server-push into a live Claude Code session on the subscription, and a cloud
cron that wakes to poll is just paid polling (conflicts with #16). So approvals
and merges leave their trace in Postgres (and on GitHub); a Higgs session
reconciles from that state in one of two modes:
- **Live work session:** Higgs runs a self-paced `/loop` that drains the
  approval/merge queue and dispatches follow-on work (mark done, unblock
  dependents, post-merge analysts) in near-real-time — on the subscription,
  only while Tyler is actively working.
- **Otherwise:** the next session start drains the queue — "since last time, N
  PRs merged; here's what's dispatched and newly unblocked."

The eventual **active ping** (a merge webhook waking a runner to dispatch
automatically) is the same deferred north-star as UI-driven compute — it
arrives with the subscription-tied runner, not before. This model keeps the
charter's discipline literal: the DB is truth and the mailbox; context windows
are scratch.

## 8. Definition of done

- All §2 surfaces built to the approved mockup; the SPA is served by the
  backend as one image and deploys to the gated service.
- Only Tyler can authenticate; ingress is locked; the placeholder `allUsers`
  binding is retired.
- No endpoint or UI affordance can spawn an agent run or call the model API.
- Backend reuses the emctl data layer (no duplicated queries); tests pass
  (backend: pytest/ruff/mypy; frontend: Vitest + typecheck); security review
  clears.
- Notes migration is additive and reversible.

## 9. Dispatch metadata

- **Project:** #3 (command-center) · **Repo:** team-higgs
- **Tasks:** #25 mockup (frontend) → #26 this PRD (em) → #27 backend
  (backend) → #28 SPA (frontend) → #29 infra (devops). Security reviews every
  PR. Only Tyler merges.

## 10. Intended state writes

- `task #26 → in_review` on this PR; `→ done` at merge.
- On approval of the mockup (task #25): `#25 → done`, unblocking #27/#28.
