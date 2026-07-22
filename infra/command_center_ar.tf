# Docker image registry for the command-center Cloud Run service (command_center.tf).
# Mirrors the plant-log pattern (artifact_registry.tf): a per-service DOCKER repo in
# the same region, with the github-ci service account granted writer on THIS repo
# only (least-privilege — no project-wide artifactregistry.writer). CI (a deferred
# deploy-workflow follow-up) pushes the built image here under WIF; Cloud Run pulls
# from here. Artifact Analysis CVE scanning is enabled at the project/API level, not
# per-repo, so there is no scanning resource here (same as plant-log).
#
# This repo is unconditional (not gated behind var.enable_command_center): the
# registry can exist and receive images before the gated service is enabled, which
# is exactly the day-zero chicken-and-egg the command_center_image default solves.
resource "google_artifact_registry_repository" "command_center" {
  location      = var.region
  repository_id = "command-center"
  format        = "DOCKER"
  description   = "Container images for the command-center Cloud Run service."
}

# Push command-center images — scoped to THIS repo, not project-wide. Non-authoritative
# _member grant (adds github-ci without disturbing other members), mirroring the
# plant-log writer binding in wif.tf. github_ci is the CI deploy service account
# (data source declared in wif.tf); WIF issues it short-lived tokens, no JSON key.
resource "google_artifact_registry_repository_iam_member" "github_ci_cc_ar_writer" {
  project    = google_artifact_registry_repository.command_center.project
  location   = google_artifact_registry_repository.command_center.location
  repository = google_artifact_registry_repository.command_center.name
  role       = "roles/artifactregistry.writer"
  member     = data.google_service_account.github_ci.member
}
