# Docker image registry for plant-log. CI (follow-up) pushes images here under
# WIF auth; Cloud Run pulls from here. Artifact Analysis on the registry provides
# post-ship CVE scanning (per docs/stack-devops.md) — enabled at the project/API
# level, not a per-repo resource.
resource "google_artifact_registry_repository" "plant_log" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  format        = "DOCKER"
  description   = "Container images for the plant-log Cloud Run service."
}
