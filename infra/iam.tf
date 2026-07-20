# -----------------------------------------------------------------------------
# Least-privilege runtime identity for the plant-log Cloud Run service.
#
# The service runs as its OWN service account (not the default compute SA) and
# is granted exactly two capabilities:
#   * connect to Cloud SQL (roles/cloudsql.client, project-scoped — the minimum
#     scope the Cloud SQL connector requires), and
#   * read ITS OWN secrets (secretAccessor granted per-secret, never project-wide).
# -----------------------------------------------------------------------------

resource "google_service_account" "plantlog_run" {
  account_id   = "plantlog-run"
  display_name = "plant-log Cloud Run runtime"
}

# Cloud SQL client is the smallest role that lets the connector open the socket.
resource "google_project_iam_member" "plantlog_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.plantlog_run.email}"
}

# Secret access is granted one secret at a time — the runtime SA can read only
# the three plant-log secrets, nothing else in the project.
resource "google_secret_manager_secret_iam_member" "database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.plantlog_run.email}"
}

resource "google_secret_manager_secret_iam_member" "session_secret" {
  secret_id = google_secret_manager_secret.session_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.plantlog_run.email}"
}

resource "google_secret_manager_secret_iam_member" "google_client_secret" {
  secret_id = google_secret_manager_secret.google_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.plantlog_run.email}"
}
