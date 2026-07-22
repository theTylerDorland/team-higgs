# =============================================================================
# CI apply identity — the roles that let GitHub Actions run Terraform apply.
#
# SECURITY-CRITICAL FILE. Every binding here is a privilege grant to a CI
# identity. Read infra/terraform-ci.md "Security surface" and the PR security
# section before changing anything.
#
#   * github-ci (existing SA) — the APPLY identity. Impersonable ONLY from
#     refs/heads/main (authoritative binding in wif.tf, task #14 hardening).
#     This file ADDS the resource-management roles Terraform apply needs.
#     WRITE access; main-ref only; never assumable from a PR.
#
# NO plan-on-PR identity. plan-on-PR would need an identity assumable from PR
# refs that can READ remote state (the state object holds the plant-log DB
# password + session secret in plaintext) and read the plant-log secrets to
# refresh secret_version resources at plan time — i.e. a PR-ref-impersonable
# identity with production-secret read. Same-repo agent PRs are this platform's
# threat model, so that identity is not created here (security review 38 / task
# #23 path A). Plan-on-PR is DEFERRED to hardening task #35 (move TF-generated
# secrets out of state first, so a plan identity no longer needs state-read).
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

# roles/iam.serviceAccountUser (project-level) — actAs on runtime service
# accounts. Deploying/updating ANY Cloud Run service requires actAs on the SA the
# service runs as; run.admin above does NOT grant it. github-ci already holds a
# resource-scoped actAs on plantlog-run (github_ci_actas_runtime, wif.tf), but
# apply now also stands up the command-center service (runs as command-center-run,
# command_center.tf) and will deploy future services with their own runtime SAs.
# Project-level serviceAccountUser is the minimum that covers actAs across all of
# them without a new per-SA binding each time. Already granted out-of-band, so
# this _member create idempotently ADOPTS the existing grant (0 destroy). See
# learning #15 (complete github-ci role set).
resource "google_project_iam_member" "github_ci_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
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

# roles/storage.admin on the Terraform STATE bucket only (not project-wide
# storage). RECONCILED from roles/storage.objectAdmin (task #37). Apply must not
# only read/write the state object and manage the state LOCK object (objectAdmin's
# scope) but ALSO REFRESH THIS RESOURCE — the state bucket's OWN IAM policy — on
# every plan/apply, which requires storage.buckets.getIamPolicy. objectAdmin does
# NOT include that permission, so a github-ci-driven run could not refresh its own
# state-bucket binding (self-referential); storage.admin (still bucket-scoped) is
# the minimum predefined role that adds it. See learning #15.
#
# NON-DESTRUCTIVE RECONCILE: github-ci ALREADY holds storage.admin on this bucket
# out-of-band, so this _member create idempotently ADOPTS the existing grant. The
# superseded objectAdmin binding is dropped as redundant, but state access is
# never revoked — storage.admin is a strict superset of objectAdmin and is present
# before, during, and after the change. The bucket is the day-zero state bucket
# (see backend.hcl); non-secret and stable.
resource "google_storage_bucket_iam_member" "github_ci_tfstate" {
  bucket = "team-higgs-platform-tfstate"
  role   = "roles/storage.admin"
  member = local.github_ci_member
}

# -----------------------------------------------------------------------------
# DNS module grants (task #36) — needed for infra/dns.tf.
#
# The Cloud DNS module (PR #31) declares google_dns_managed_zone /
# google_dns_record_set (needs roles/dns.admin) and google_project_service.dns
# (needs roles/serviceusage.serviceUsageAdmin to manage API enablement). github-ci
# held NEITHER, so the first apply-on-merge over the DNS module failed. These two
# additive _member grants close that gap. Both are project-scoped: dns.admin has
# no narrower predefined role that can create zones + record sets, and service
# enablement is inherently a project-level operation.
#
# SELF-GRANT within a single apply: github-ci already holds
# roles/resourcemanager.projectIamAdmin (above), so the SAME apply-on-merge run
# that adds these two bindings is authorized to write them — no manual pre-grant
# by Tyler. The only hazard is IAM propagation lag: a freshly written binding is
# not always effective the instant the resource create call fires. The time_sleep
# below absorbs that lag (see its comment). This is a PRIVILEGE EXPANSION of the
# CI identity — flagged for security review (PR "Surface").
# -----------------------------------------------------------------------------

# roles/dns.admin — create/manage the two managed zones and every record set in
# infra/dns.tf. (No resource-scoped DNS role exists for zone creation.)
resource "google_project_iam_member" "github_ci_dns_admin" {
  project = var.project_id
  role    = "roles/dns.admin"
  member  = local.github_ci_member
}

# roles/serviceusage.serviceUsageAdmin — manage google_project_service.dns
# (enable/own the dns.googleapis.com service). serviceUsageConsumer can only USE
# enabled services, not manage enablement, so admin is the minimum that lets
# Terraform own the API-enablement resource.
resource "google_project_iam_member" "github_ci_serviceusage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = local.github_ci_member
}

# IAM-propagation barrier (task #36). github-ci self-grants the two roles above in
# THIS apply, but GCP IAM changes propagate asynchronously — a zone/create call
# issued microseconds after the binding write can still see the OLD policy and
# 403. This time_sleep forces a fixed pause AFTER the two bindings are written and
# BEFORE anything that needs them runs. google_project_service.dns and both DNS
# zones depend_on it (infra/dns.tf), so within one apply-on-merge run the order is:
# write bindings -> wait 90s -> enable dns.googleapis.com + create zones. The wait
# only runs when this resource is first CREATED; once it is in state, subsequent
# applies do not re-pause. 90s is comfortably above observed project-IAM
# propagation, without materially slowing the pipeline.
resource "time_sleep" "dns_iam_propagation" {
  create_duration = "90s"

  depends_on = [
    google_project_iam_member.github_ci_dns_admin,
    google_project_iam_member.github_ci_serviceusage_admin,
  ]
}
