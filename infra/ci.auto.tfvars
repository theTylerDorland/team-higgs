# =============================================================================
# CI Terraform variables — COMMITTED, NON-SECRET, AUTHORITATIVE.
#
# Auto-loaded by Terraform (every `*.auto.tfvars` is), so the apply-on-merge job
# gets its inputs with zero workflow wiring. This file is the single source of
# truth for the module's deployment-specific values; it is reviewed in PRs like
# any other code and changes go through the same merge gate.
#
# WHY committed .auto.tfvars over workflow `env`/TF_VAR_*:
#   * Reviewable + versioned: a value change shows up in the PR diff and the
#     plan, under the same governance as the HCL.
#   * Applied exactly as reviewed: the merge run reads this same committed file.
#   * Keeps the workflow YAML minimal and free of environment-specific values.
#
# NON-SECRET ONLY. Every value here is safe to commit: a GCP project ID, a
# region, household email allow-list, a public OAuth *client ID* (sent to
# browsers), public URLs, and a public placeholder image. The OAuth client
# SECRET is NOT here and never will be — it lives in Secret Manager
# (plantlog-google-client-secret), set out-of-band. Do not add a secret to this
# file; if a value would be a security finding in a workflow file, it is one
# here too.
#
# NOTE: this supersedes the local, gitignored terraform.tfvars for these keys.
# `*.auto.tfvars` overrides terraform.tfvars, so keep the two consistent or
# remove the now-redundant local terraform.tfvars to avoid confusion.
# =============================================================================

project_id = "team-higgs-platform"
region     = "us-central1"

# plant-log Google sign-in allow-list: the household accounts (NOT secret).
allowed_emails = "tyler.dorland@gmail.com,flowertracey@gmail.com,tyler@tylerdorland.com"

# plant-log Google OAuth — client ID is public; the client SECRET is in Secret
# Manager, never here.
google_client_id    = "565122789946-kv5kjk0qvlrfm6koq3j7sbf98123pek1.apps.googleusercontent.com"
google_redirect_uri = "https://airportbar.app/api/auth/callback"

# Apex canonical host: activates the www->apex 301 in the plant-log backend.
canonical_host = "airportbar.app"

# higgs-command placeholder image (disposable hello page; image changes are
# ignored by lifecycle, so this only matters on first create).
higgs_command_image = "us-docker.pkg.dev/cloudrun/container/hello"

# Command center (command_center.tf) — ENABLED (task #37). Flipping this from
# false to true un-gates every command_center.tf resource (count 0 -> 1): the
# gated Cloud Run service, its least-privilege runtime SA, its four Secret Manager
# containers + placeholder versions + per-secret IAM. This is the FIRST create of
# these resources (they were never in state while gated off), so the flip is pure
# add, zero destroy.
#
# The service comes up LOCKED: ingress = INTERNAL_LOAD_BALANCER and NO allUsers
# run.invoker binding (command_center.tf), so it is unreachable from the open
# internet by construction. Reachability (the IAP-fronted external HTTPS load
# balancer) is the SEPARATE epic, task #33 — not this PR.
enable_command_center = true

# Command-center Google OAuth client ID — PUBLIC, NON-SECRET (it is sent to every
# browser that hits the sign-in page). The matching client SECRET is NOT here; it
# lives in Secret Manager (command-center-google-client-secret), set out-of-band.
# A non-empty value both wires real OIDC AND arms the backend's fail-closed
# DEV_AUTH guard (command_center/config.py); with the service now enabled, the
# variable's validation requires it to be non-empty (variables.tf).
cc_google_client_id = "565122789946-540lt8tjf813lhsu3kmacb9o82boc4cf.apps.googleusercontent.com"
