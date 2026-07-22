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

output "dns_zone_nameservers" {
  description = "Cloud DNS nameservers per zone. These are the values Tyler sets at the registrar to delegate each domain (the ONE-TIME manual NS switch in infra/dns-cutover.md). Read after apply; do NOT switch NS until replication is verified."
  value = {
    "airportbar.app"   = google_dns_managed_zone.airportbar_app.name_servers
    "tylerdorland.com" = google_dns_managed_zone.tylerdorland_com.name_servers
  }
}

output "secret_ids" {
  description = "Secret Manager secret IDs the service reads at runtime."
  value = {
    database_url         = google_secret_manager_secret.database_url.secret_id
    session_secret       = google_secret_manager_secret.session_secret.secret_id
    google_client_secret = google_secret_manager_secret.google_client_secret.secret_id
  }
}

# --- command center -----------------------------------------------------------

# The command center is gated behind var.enable_command_center (task #36); when
# it is false these resources are count=0, so each output resolves to null via
# `one(...)` rather than erroring on a missing [0] index.
output "command_center_service_name" {
  description = "Name of the gated command-center Cloud Run service (ingress-locked; not publicly invokable). null while enable_command_center = false."
  value       = one(google_cloud_run_v2_service.command_center[*].name)
}

output "command_center_runtime_service_account" {
  description = "Email of the command-center Cloud Run runtime service account (grant it as the run.invoker target from the IAP/LB service agent at fronting time). null while enable_command_center = false."
  value       = one(google_service_account.command_center_run[*].email)
}

output "command_center_secret_ids" {
  description = "Secret Manager secret IDs the command-center service reads at runtime (each null while enable_command_center = false). Tyler sets the real values for the client secret and the GitHub merge token out-of-band; DATABASE_URL is set at the Phase-3 state-store migration."
  value = {
    session_secret       = one(google_secret_manager_secret.cc_session_secret[*].secret_id)
    google_client_secret = one(google_secret_manager_secret.cc_google_client_secret[*].secret_id)
    github_token         = one(google_secret_manager_secret.cc_github_token[*].secret_id)
    database_url         = one(google_secret_manager_secret.cc_database_url[*].secret_id)
  }
}
