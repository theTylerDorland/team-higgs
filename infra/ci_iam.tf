# =============================================================================
# CI apply/plan identities — the roles that let GitHub Actions run Terraform.
#
# SECURITY-CRITICAL FILE. Every binding here is a privilege grant to a CI
# identity. Read infra/terraform-ci.md "SA grant delta" and the PR security
# section before changing anything. Two identities, deliberately split:
#
#   * github-ci  (existing SA) — the APPLY identity. Impersonable ONLY from
#     refs/heads/main (authoritative binding in wif.tf, task #14 hardening).
#     This file ADDS the resource-management roles Terraform apply needs.
#     WRITE access; main-ref only; never assumable from a PR.
#
#   * terraform-plan (new SA) — the PLAN identity. Impersonable from any ref
#     of TeamHiggs/team-higgs (so pull_request workflows can run `terraform
#     plan`). READ-ONLY: it cannot create, modify, or destroy anything. It
#     CAN read remote state and the three plant-log secret values (an
#     unavoidable consequence of refreshing google_secret_manager_secret_version
#     at plan time — see below and the PR "Surface" section).
#
# WHY TWO SAs: plan-on-PR needs an identity assumable from PR refs; apply needs
# an identity with broad write. Granting the ONE identity both (PR-ref trust AND
# write/admin) would expose a project-admin identity to pre-merge PR workflow
# code — exactly what the main-ref hardening on github-ci prevents. Splitting
# keeps the powerful identity (github-ci) main-ref-only and gives PRs a
# least-privilege read-only identity instead. See PR Deviations.
# =============================================================================

# -----------------------------------------------------------------------------
# github-ci — APPLY identity: resource-management roles.
#
# Every role below is justified against the specific resources in this module
# that Terraform apply must create/update. These are project-scoped where the
# managed action is inherently project-level (creating SAs, setting project IAM,
# managing WIF pools); resource-scoped is not available for those operations.
# All are NON-authoritative _member grants (additive; they do not disturb any
# other member). This is a PRIVILEGE EXPANSION of the CI identity — flagged for
# security review (PR "Surface").
#
# NOTE on overlap: github-ci already holds three tighter, resource-scoped deploy
# grants in wif.tf (artifactregistry.writer on the plant-log repo, run.developer
# on the plant-log service, serviceAccountUser on plantlog-run). Those serve the
# plant-log IMAGE-DEPLOY workflow (a separate repo/pipeline). run.admin and
# artifactregistry.admin below strictly superset the first two; serviceAccountUser
# (actAs plantlog-run) is NOT supersetted and is REQUIRED by apply too (deploying
# a Cloud Run service that runs as plantlog-run needs actAs on it). The scoped
# grants are intentionally LEFT in place (removing them touches the plant-log
# deploy path, out of scope here) — consolidation is a proposed follow-up.
# -----------------------------------------------------------------------------

locals {
  # github-ci's IAM member string (serviceAccount:github-ci@...); the SA itself
  # is a day-zero precondition, read read-only via the data source in wif.tf.
  github_ci_member = data.google_service_account.github_ci.member
}

# roles/run.admin — manages BOTH Cloud Run v2 services (plant-log, higgs-command),
# their custom-domain mappings, and their IAM policy bindings (public invoke).
# The existing scoped run.developer cannot create services, create domain
# mappings, or setIamPolicy on a service; run.admin is the minimum predefined
# role that covers all three across the two services.
resource "google_project_iam_member" "github_ci_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = local.github_ci_member
}

# roles/cloudsql.admin — manages the shared Postgres instance, the plantlog
# database, and the plantlog user. Creating instances/databases/users has no
# narrower predefined role. prevent_destroy + deletion_protection still guard
# the instance against a destroy plan.
resource "google_project_iam_member" "github_ci_cloudsql_admin" {
  project = var.project_id
  role    = "roles/cloudsql.admin"
  member  = local.github_ci_member
}

# roles/secretmanager.admin — manages the three secret CONTAINERS, their
# versions, and their per-secret IAM bindings (secretAccessor grants to
# plantlog-run in iam.tf). Creating a secret AND setting its IAM policy requires
# admin; secretVersionManager cannot create secrets or set IAM.
resource "google_project_iam_member" "github_ci_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = local.github_ci_member
}

# roles/artifactregistry.admin — manages the plant-log Docker repository AND its
# IAM binding (github_ci_ar_writer in wif.tf). Creating a repo + setIamPolicy on
# it requires admin. Supersets the existing scoped artifactregistry.writer.
resource "google_project_iam_member" "github_ci_artifactregistry_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = local.github_ci_member
}

# roles/iam.serviceAccountAdmin — creates the plantlog-run runtime SA and sets
# IAM policy on service accounts: the authoritative github_ci_wif binding on
# github-ci itself, and github_ci_actas_runtime on plantlog-run (both in wif.tf).
# SECURITY NOTE: this lets github-ci setIamPolicy on service accounts, including
# its OWN impersonation binding. That is inherent in letting CI manage the WIF
# binding via Terraform. Flagged for security review.
resource "google_project_iam_member" "github_ci_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = local.github_ci_member
}

# roles/iam.workloadIdentityPoolAdmin — manages the WIF pool + provider in
# wif.tf (the trust plane itself). SECURITY NOTE: this lets github-ci modify the
# very federation trust that admits it. Inherent in codifying WIF in Terraform
# and applying it from CI. Flagged for security review.
resource "google_project_iam_member" "github_ci_wif_pool_admin" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = local.github_ci_member
}

# roles/resourcemanager.projectIamAdmin — manages the ONE project-level IAM
# binding in this module: plantlog_cloudsql_client (roles/cloudsql.client to
# plantlog-run). roles/cloudsql.client can only be granted at project level, so
# managing it requires project setIamPolicy.
#
# HIGHEST-BLAST-RADIUS GRANT. projectIamAdmin lets the holder grant ANY role to
# ANY principal at the project — i.e. it is escalation-complete (github-ci could
# grant itself owner). It is REQUIRED only for that single cloudsql.client
# binding. Recommended mitigations (proposed follow-ups, PR "Follow-ups"):
#   (a) replace with a custom role limited to project get/setIamPolicy; or
#   (b) move plantlog_cloudsql_client out of CI-managed Terraform (grant once by
#       hand, drop the resource), removing the need for this role entirely.
# Flagged as the top security-review item.
resource "google_project_iam_member" "github_ci_project_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = local.github_ci_member
}

# roles/storage.objectAdmin on the Terraform STATE bucket only (not project-wide
# storage). Apply reads/writes the state object and creates/deletes the state
# LOCK object; objectAdmin scoped to the single bucket is the standard,
# well-understood grant for a Terraform GCS backend. The bucket name is the
# day-zero state bucket (see backend.hcl); it is non-secret and stable.
# (A slightly tighter roles/storage.objectUser is a possible follow-up.)
resource "google_storage_bucket_iam_member" "github_ci_tfstate" {
  bucket = "team-higgs-platform-tfstate"
  role   = "roles/storage.objectAdmin"
  member = local.github_ci_member
}

# -----------------------------------------------------------------------------
# terraform-plan — PLAN identity (new SA): READ-ONLY, PR-ref-trusted.
#
# Runs `terraform plan` on pull_request workflows. It can read every resource's
# live state (to compute the diff) and read remote state, but holds NO write or
# admin role — a compromised/malicious PR workflow assuming it cannot modify
# infrastructure.
#
# UNAVOIDABLE EXPOSURE (flagged for security review): refreshing the three
# google_secret_manager_secret_version resources at plan time requires
# secretmanager.versions.access on those secrets, so this identity CAN read the
# plant-log database URL, session secret, and OAuth client-secret values. Any
# identity that can run a real `terraform plan` over this module has that
# capability; splitting it into a read-only, per-secret-scoped SA is the tightest
# posture available. If security judges even read-only secret exposure to PR-ref
# workflows unacceptable, the fallback is to drop plan-on-PR and keep only
# apply-on-merge (see PR "Follow-ups" / runbook).
# -----------------------------------------------------------------------------

resource "google_service_account" "terraform_plan" {
  account_id   = "terraform-plan"
  display_name = "Terraform plan-on-PR (read-only)"
}

# WIF trust: any ref of TeamHiggs/team-higgs may impersonate terraform-plan.
# Keyed on attribute.repository (not attribute.ref) so pull_request refs
# (refs/pull/N/merge) are covered, but scoped to the ONE repo infra PRs come
# from — plant-log workflows cannot assume it. The provider's own
# attribute_condition still gates which repos may mint a token at all.
# _member (additive), not _binding: this is a fresh SA with no other trust.
resource "google_service_account_iam_member" "terraform_plan_wif" {
  service_account_id = google_service_account.terraform_plan.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/TeamHiggs/team-higgs"
}

# Broad project READ so plan can refresh every managed resource type (Cloud Run,
# Cloud SQL, Artifact Registry, service accounts, WIF, project IAM). roles/viewer
# grants no write and no secret-VALUE access. (Tightening to per-service viewer
# roles is a possible follow-up.)
resource "google_project_iam_member" "terraform_plan_viewer" {
  project = var.project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${google_service_account.terraform_plan.email}"
}

# Read the remote state object. objectViewer (read-only): plan runs with
# -lock=false so it never needs to write the lock object.
resource "google_storage_bucket_iam_member" "terraform_plan_tfstate" {
  bucket = "team-higgs-platform-tfstate"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.terraform_plan.email}"
}

# secretmanager.versions.access on EXACTLY the three plant-log secrets (per
# secret, never project-wide) — required to refresh the secret_version resources
# at plan time. This is the exposure noted in the block header above.
resource "google_secret_manager_secret_iam_member" "terraform_plan_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.terraform_plan.email}"
}

resource "google_secret_manager_secret_iam_member" "terraform_plan_session_secret" {
  secret_id = google_secret_manager_secret.session_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.terraform_plan.email}"
}

resource "google_secret_manager_secret_iam_member" "terraform_plan_google_client_secret" {
  secret_id = google_secret_manager_secret.google_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.terraform_plan.email}"
}
