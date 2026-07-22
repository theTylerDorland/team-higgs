# DevOps Stack — Decisions

Authoritative record of the platform's infrastructure and delivery choices.
Agents conform to this document; changes to it are PRs with Tyler's merge.

## Decisions

**Cloud: GCP.** All new infrastructure targets GCP. Prior Azure work does
not constrain this platform.

**CI/CD: GitHub Actions.** All automation — reviews, docs-on-merge, task
triggers, deploys, scheduled passes (via Actions cron) — runs in Actions.
No second automation system.

**Compute: Cloud Run.** Every service (emctl API, EM service, product
backends, the UI) ships as a Docker image deployed to Cloud Run. GKE is
not used; a proposal to introduce it must argue against Cloud Run
specifically, not just for Kubernetes generally.

**Database: Cloud SQL for Postgres.** One instance for the platform state
store; product databases as separate databases on the same instance until
load argues otherwise.

**Images: Artifact Registry**, with **Artifact Analysis** providing
registry-layer CVE scanning (the post-ship complement to PR-time
pip-audit/Trivy gates).

**Secrets: Secret Manager.** Nothing secret in repos, env files, or
workflow definitions. Services read secrets at runtime via their service
identity.

**CI → GCP auth: Workload Identity Federation.** GitHub Actions
authenticates via short-lived OIDC tokens. Long-lived service-account JSON
keys are prohibited — a key appearing anywhere is a security blocker
finding.

**IaC: Terraform, from the start.** All GCP resources are declared in
`infra/` in the platform repo. Rationale: infrastructure changes become
PRs, which puts them through the same review panel and merge gate as
everything else. Console-created resources are invisible to the governance
system and are treated as drift.

**Docs publishing: MkDocs → GitHub Pages.** No cloud dependency.

**Edge & access: Cloud Load Balancing + Identity-Aware Proxy (IAP).**
Adopted by the command-center reachability epic (#33) to make the one
deployed surface that can merge PRs reachable *only* through a
Google-managed front door — never openly invokable. The command-center
Cloud Run service runs ingress `INTERNAL_LOAD_BALANCER` with its sole
invoker the IAP service agent (never `allUsers`); a global external HTTPS
Application Load Balancer fronts it — static anycast IP → target HTTPS
proxy terminating a Google-managed cert for `higgs.tylerdorland.com` → URL
map → backend service with IAP enabled → serverless NEG → Cloud Run. IAP
authenticates the user at the edge and enforces
`roles/iap.httpsResourceAccessor` (Tyler only); the app's own Google OIDC
stays on behind it as defence-in-depth. Justification: emctl decision #24
(command-center reachability, Option A). Standing cost: an external HTTPS
LB carries a ~$18–25/mo baseline even at zero traffic.

## Compute and billing — dual-path (while Tyler is the sole user)

The platform runs on Tyler's Claude **subscription**, not API billing, for as
long as he is the only user. This determines where each layer runs:

- **Model compute stays local, on the subscription.** The EM and every
  dispatched agent run in Tyler's local Claude Code / Agent SDK session under
  his own login (OAuth profile). **Nothing deployed to the cloud ever calls
  Claude** — that is the line that keeps us off API billing.
- **State is the integration seam.** The Postgres store (local now, Cloud SQL
  at Phase 3) is what the local agent and any deployed surface share. Because
  the agent and the UI both talk to the *database*, not to each other, they
  deploy independently.
- **The UI deploys; it does not compute.** A deployed UI (Cloud Run) is a
  dashboard + async intake queue over the state store: it reads/writes rows,
  makes **no model calls**, and needs no API key. Tyler drops intent through
  it as a row; the local EM picks it up and does the work on the subscription.

**What would force API billing (deferred until Tyler decides, informed by
measured cost):**
- **Unattended cloud automation** — e.g. a PR auto-reviewed with no local
  session running — needs a model call in CI. Deferred; the interactive local
  loop covers a solo user.
- **Cloud-side synchronous chat** — real-time chat handled server-side is a
  model call in the cloud. On the subscription, synchronous chat stays local
  (in Claude Code); the deployed UI is async.

**Cost before commitment.** Every agent run records its token cost in `runs`;
the `hypothetical_api_cost` metric projects what the API-billed path would
cost from that ledger. *Accurate* projection needs token usage recorded **by
type** — input, output, and cache tokens are priced very differently (output
is ~5× input on Opus) — so until `runs` captures that split the metric reports
a cost *range*, not a point. Build on the subscription, watch the ledger,
price the API path from real usage before adopting it.

Note: mechanical CI (tests, lint, type-check on a PR) runs **no** Claude calls,
so it is compatible with the subscription model and can be adopted
independently of the API-billing question.

## Terraform discipline

- Remote state in a GCS bucket with versioning; nobody edits state by hand.
- Every infra PR includes the `terraform plan` output as an attached
  artifact. Reviewers and Tyler review the plan, not just the HCL — the
  plan is what will actually happen.
- `terraform apply` runs **only** in the merge-triggered workflow via WIF.
  No agent and no human applies from a laptop after day zero. Merging the
  PR is the deploy decision; there is no second lever.
- `prevent_destroy` on stateful resources (Cloud SQL, state bucket).
  Destroy operations are never automated.

## Workflow (Actions) discipline

- Third-party actions pinned by commit SHA, not tag.
- Every workflow declares a least-privilege `permissions:` block.
- Workflow changes ship in isolated PRs (see implementer-devops) and
  always receive security review.

## Security invariant: the command-center gate rests on WIF ref-scoping, not IAM

The command-center service can merge PRs, so the integrity of its IAP gate
is a platform-critical invariant. PR #38's security review surfaced that
this gate does **not** currently rest on IAP IAM role scoping. `github-ci`
holds `roles/resourcemanager.projectIamAdmin` — an escalation-complete
grant: CI can rewrite any IAM binding in the project, the IAP allowlist
included. What actually keeps the gate closed today is repo-level controls,
not IAM — and the load-bearing one is WIF ref-scoping:

- **WIF main-ref scoping** (`infra/wif.tf`) — the enforced control. CI's
  short-lived GCP credentials are issued only for `refs/heads/main`, so
  nothing off a feature branch can apply infrastructure (verified in
  `wif.tf`).
- **team-higgs `main` merge control** — only Tyler (org admin) can merge
  to `main`. This leg is weaker than it looks: the configured review is
  org-admin-bypassable and no required status checks gate merge today, so
  review is not itself a hard gate. Closing that branch-protection-
  enforcement gap (adding required status checks) is tracked by task #41.

Forward-looking rule: **until the `projectIamAdmin` grant is narrowed,
every infra change must preserve WIF main-ref-scoping (and Tyler-only
merge) as the real gate.** Do not introduce any path that applies
infrastructure outside a merged-to-`main` change. Narrowing the CI grant is
tracked by task #40; closing the branch-protection-enforcement gap
(required status checks) by task #41.

## Day zero (Tyler, once, by hand)

Terraform cannot bootstrap its own preconditions. One supervised session:

1. Create the GCP project; enable APIs (Run, SQL Admin, Artifact Registry,
   Secret Manager, IAM Credentials).
2. Create the Terraform state bucket (versioned).
3. Create the WIF pool/provider and the CI service account, bound to the
   GitHub repo.
4. Run the initial `terraform apply` locally under your own gcloud auth to
   stand up the base stack.
5. From then on, CI owns apply; local applies end here.

Do this interactively in Claude Code rather than alone — each step is one
or two gcloud/terraform commands, and the session doubles as your record
of what exists and why.

## Deferred (deliberately undecided)

- Multi-environment promotion (dev/staging/prod) — one environment until a
  customer-facing product forces the split; revisit at that PRD.
- Dashboards, SLOs, alert routing — Cloud Logging/Monitoring collects from
  day one; alert design is a task when there is something to page about.
- Production alert → EM intake (the "bug catching" loop) — phase 2;
  reuses the async machinery, needs only the webhook path.
- Local model serving infrastructure — decided alongside the model-routing
  work, not before.
