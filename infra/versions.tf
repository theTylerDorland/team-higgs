# Terraform + provider pinning and remote state backend.
#
# Remote state lives in a *versioned* GCS bucket (a day-zero manual
# precondition — Terraform cannot create the bucket that holds its own state).
# The bucket name is environment-specific and is supplied at `init` time via
# partial backend config so no project-specific value is committed here:
#
#   terraform init -backend-config=backend.hcl
#
# See backend.hcl.example and infra/README.md.
terraform {
  required_version = ">= 1.7.0"

  backend "gcs" {
    # bucket = "<supplied via backend.hcl>"
    prefix = "infra"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
