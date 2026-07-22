# Terraform CI — plan-on-PR, apply-on-merge (runbook)

`.github/workflows/terraform.yml` runs Terraform in GitHub Actions:

| Trigger | Job | Identity | What runs |
|---|---|---|---|
| `pull_request` touching `infra/**` | `plan` | `terraform-plan` SA (**read-only**) | `fmt -check`, `validate`, `plan`; posts the plan as a sticky PR comment |
| `push` to `main` touching `infra/**` | `apply` | `github-ci` SA (write/admin, **main-ref only**) | `terraform apply -auto-approve` |

**The merge is the deploy decision.** There is no separate apply approval and no
manual environment gate (Tyler's call, task #23). Merging a PR that changed
`infra/` applies it. Local `terraform apply` ends here.

## Why two service accounts

`plan` must run on PR branches; `apply` must have broad write. Giving one
identity both PR-ref trust *and* write/admin would expose a project-admin
identity to pre-merge PR workflow code — which is exactly what the `github-ci`
main-ref hardening (task #14) prevents. So:

- **`github-ci`** — the APPLY identity. Its WIF binding is authoritative to
  `attribute.ref/refs/heads/main` (unchanged by this work). It holds the
  resource-management roles in `ci_iam.tf`. Never assumable from a PR.
- **`terraform-plan`** — the PLAN identity (new). Assumable from any ref of
  `TeamHiggs/team-higgs` (so PR workflows can plan), but holds **no write role**
  — only project `viewer`, state-bucket `objectViewer`, and per-secret
  `secretAccessor` on the three plant-log secrets. A compromised PR workflow
  assuming it cannot change infrastructure.

  **Known exposure:** refreshing the `google_secret_manager_secret_version`
  resources at plan time requires reading those secret values, so
  `terraform-plan` can read the plant-log DB URL, session secret, and OAuth
  client secret. Any identity that can run a real plan over this module has that
  capability; the read-only, per-secret-scoped SA is the tightest posture. In
  practice PR-ref OIDC is only issued to same-repo branches (fork PRs get no
  `id-token`), and all actions are SHA-pinned. If security judges this
  unacceptable, drop the `plan` job and keep only `apply` (see Follow-ups).

## State and locking

Remote state is the versioned GCS bucket `team-higgs-platform-tfstate`
(`versions.tf` backend, `backend.hcl`). The GCS backend locks automatically:
`apply` acquires a lock object (github-ci has `storage.objectAdmin` on the
bucket); `plan` runs `-lock=false` and never writes the lock. Concurrency in the
workflow serializes runs per ref so main applies never overlap.

## tfvars

CI variables live in committed **`infra/ci.auto.tfvars`** — NON-SECRET only
(project id, region, email allow-list, OAuth *client ID*, public URLs,
placeholder image). Terraform auto-loads `*.auto.tfvars`, so both jobs get
identical inputs with no workflow wiring. Chosen over workflow `env`/`TF_VAR_*`
because the values are then reviewed in the PR diff and the plan, versioned
under the same gate, and can't drift between the plan and apply jobs.

The OAuth client **secret** is NOT in CI — it stays in Secret Manager
(`plantlog-google-client-secret`), set out-of-band. `ci.auto.tfvars` is the
authoritative committed config and supersedes the local, gitignored
`terraform.tfvars` for its keys (`.auto.tfvars` overrides `terraform.tfvars`);
keep them consistent or remove the redundant local file.

## One-time setup (Tyler, once)

CI cannot apply the change that grants CI its own permissions — the same
bootstrap caveat as day zero / the WIF import (see `README.md`). Before CI can
run Terraform:

1. **Repo variable** `WIF_PROVIDER` = the full provider resource name:
   ```sh
   gh variable set WIF_PROVIDER --repo TeamHiggs/team-higgs \
     --body "$(cd infra && terraform output -raw wif_provider_name)"
   ```
   (The two SA emails are hard-coded in the workflow; only the provider path,
   which embeds the project number, is a variable.)

2. **Bootstrap apply** (local, Tyler's own gcloud ADC) of THIS PR after merge —
   it creates the `github-ci` management roles, the `terraform-plan` SA, its WIF
   trust, and its roles. Review the plan first:
   ```sh
   cd infra
   terraform init -backend-config=backend.hcl
   terraform plan -out plan.tfplan     # expect: creates only (roles + new SA)
   terraform apply plan.tfplan
   ```
   From the **next** infra PR onward, CI owns apply; this is the last local one.

## How apply-on-merge behaves

- Merge a PR that changed `infra/**` → the `apply` job runs on the push to
  `main` → `terraform apply -auto-approve`.
- A plan that would **destroy a stateful resource** (Cloud SQL instance, state
  bucket — `prevent_destroy`) makes `apply` **error out** instead of destroying.
  That is the guard working; fix the change, don't force it.
- Image changes are ignored (`lifecycle.ignore_changes` on Cloud Run images), so
  apply never reverts a shipped revision.

## Rollback

- **Bad Terraform change:** `git revert` the merge commit and merge the revert —
  CI applies it, returning infra to the prior declared state. This is the normal
  path; state is code.
- **Bad Cloud Run revision (image):** Terraform doesn't manage the running image
  (`ignore_changes`); roll back with
  `gcloud run services update-traffic <svc> --to-revisions <prev>=100`.
- **Failed apply (main and live diverged):** the run log shows what applied.
  Land a corrective PR. Do **not** hand-edit state or run `-target`; state
  surgery is off-limits without a task saying so. Object versioning on the state
  bucket is the last-resort recovery, Tyler-only.
- **Stuck lock** (killed run): `terraform force-unlock <LOCK_ID>` locally, Tyler,
  only after confirming no apply is in flight.

## Security surface (summary)

The full grant delta and its blast-radius ranking is in the PR "Surface"
section; `ci_iam.tf` documents each binding inline. Headline: `github-ci` gains
project-scoped `run.admin`, `cloudsql.admin`, `secretmanager.admin`,
`artifactregistry.admin`, `iam.serviceAccountAdmin`,
`iam.workloadIdentityPoolAdmin`, and — highest blast radius —
`resourcemanager.projectIamAdmin`, plus `storage.objectAdmin` on the state
bucket. This makes `github-ci` an effectively project-admin identity; it stays
main-ref-only. Proposed mitigations are in the PR Follow-ups.
