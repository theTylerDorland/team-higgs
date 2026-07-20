# The Google provider is configured entirely from variables — no project ID or
# region is ever hard-coded. Credentials are NOT configured here: on day zero
# Terraform runs under Tyler's own `gcloud` application-default credentials, and
# from then on CI authenticates via Workload Identity Federation (short-lived
# OIDC tokens). No service-account key file is ever referenced.
provider "google" {
  project = var.project_id
  region  = var.region
}
