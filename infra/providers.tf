# The Google provider is configured entirely from variables — no project ID or
# region is ever hard-coded. Credentials are NOT configured here: on day zero
# Terraform runs under Tyler's own `gcloud` application-default credentials, and
# from then on CI authenticates via Workload Identity Federation (short-lived
# OIDC tokens). No service-account key file is ever referenced.
provider "google" {
  project = var.project_id
  region  = var.region
}

# google-beta is configured identically to the GA provider (no credentials here;
# same WIF/ADC path). It exists solely for google_project_service_identity in
# infra/command_center_lb.tf, which has no GA equivalent.
provider "google-beta" {
  project = var.project_id
  region  = var.region
}
