output "cloud_run_url" {
  description = "Public URL of the plant-log Cloud Run service (set GOOGLE_REDIRECT_URI from this after the first deploy)."
  value       = google_cloud_run_v2_service.plant_log.uri
}

output "sql_connection_name" {
  description = "Cloud SQL instance connection name (PROJECT:REGION:INSTANCE), as used in the Cloud SQL socket path."
  value       = google_sql_database_instance.platform.connection_name
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repo path for plant-log images."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.plant_log.repository_id}"
}

output "runtime_service_account" {
  description = "Email of the plant-log Cloud Run runtime service account."
  value       = google_service_account.plantlog_run.email
}

output "wif_provider_name" {
  description = "Full resource name of the GitHub WIF provider; use as `workload_identity_provider` in google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "ci_service_account" {
  description = "Email of the github-ci service account that CI impersonates via WIF for terraform APPLY (push to main); use as `service_account` in google-github-actions/auth in the apply job."
  value       = data.google_service_account.github_ci.email
}

output "terraform_plan_service_account" {
  description = "Email of the read-only terraform-plan service account that PR workflows impersonate via WIF for terraform PLAN; use as `service_account` in google-github-actions/auth in the plan job."
  value       = google_service_account.terraform_plan.email
}

output "secret_ids" {
  description = "Secret Manager secret IDs the service reads at runtime."
  value = {
    database_url         = google_secret_manager_secret.database_url.secret_id
    session_secret       = google_secret_manager_secret.session_secret.secret_id
    google_client_secret = google_secret_manager_secret.google_client_secret.secret_id
  }
}
