# -----------------------------------------------------------------------------
# Command center — the REAL, gated Cloud Run service (PRD command-center §6/§7,
# decisions #17/#21, platform risk #3). This is NOT the `higgs-command`
# placeholder (infra/higgs_command.tf): it is its own service, its own
# least-privilege identity, its own secrets, and — critically — it is NOT bound
# to `allUsers`. The placeholder keeps answering higgs.tylerdorland.com until the
# locked fronting is stood up; the cutover (domain move + placeholder retirement)
# is a sequenced runbook step, see the PR. Nothing here removes the placeholder.
#
# GATED (task #36): every resource in this file is behind
# `count = var.enable_command_center ? 1 : 0`, default false. The command center
# is stood up by the reachability epic (task #33) with a real cc_google_client_id;
# until then these resources are count=0 and NOT in Terraform state, so the flag
# being off is a true no-op (zero creates, zero destroys) and the apply-on-merge
# pipeline is never blocked by the required-OIDC-client-id precondition.
#
# WHAT EACH GCP PIECE DOES (for the backend engineer reading this in review):
#   * google_service_account.command_center_run — the identity the container runs
#     as. It is granted exactly two things: read its own four secrets, and open a
#     Cloud SQL socket. Nothing project-wide.
#   * google_secret_manager_secret.* (×4) — encrypted value stores. The container
#     reads them at runtime by *reference*; no secret value is in this repo, in
#     tfvars, or in the workflow. Session secret is Terraform-generated (same
#     accepted state-boundary as plant-log); the Google client secret, the GitHub
#     merge token, and the DATABASE_URL are placeholders Tyler/Phase-3 fill in
#     out-of-band (see PR "Tyler-only steps").
#   * google_cloud_run_v2_service.command_center — the service itself. Ingress is
#     locked to INTERNAL_LOAD_BALANCER and there is deliberately NO run.invoker
#     binding, so the service is unreachable from the open internet by
#     construction. It becomes reachable only once the IAP-fronted external HTTPS
#     load balancer lands (proposed in the PR; sequenced follow-up). This is the
#     safe ordering: we never expose the service first and lock it later.
# -----------------------------------------------------------------------------

# --- Least-privilege runtime identity ----------------------------------------

resource "google_service_account" "command_center_run" {
  count        = var.enable_command_center ? 1 : 0
  account_id   = "command-center-run"
  display_name = "command-center Cloud Run runtime"
}

# Cloud SQL client: the smallest role that lets the Cloud SQL connector open the
# socket to the shared platform instance. The command center reuses emctl's data
# layer, so it talks to the platform state store (the emctl Postgres). NOTE: that
# state store lives on Cloud SQL only from Phase 3 (docs/stack-devops.md,
# "State is the integration seam … local now, Cloud SQL at Phase 3"); until that
# lands, DATABASE_URL is a placeholder and DB-backed endpoints are not live. The
# service still boots and passes /healthz (a static probe), so the wiring is
# correct and complete ahead of the state-store migration. See PR "Not done".
resource "google_project_iam_member" "command_center_cloudsql_client" {
  count   = var.enable_command_center ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.command_center_run[0].email}"
}

# --- Secret Manager: the service's four runtime secrets ----------------------
# Containers + IAM are Terraform's job; real values are NOT (decision #21 for the
# token; out-of-band for the OAuth client secret; Phase 3 for DATABASE_URL). The
# session secret is the one Terraform generates, matching plant-log's proven
# pattern (the generated value lands in the versioned, access-controlled GCS
# state bucket — the same trust boundary as Secret Manager).

# SESSION_SECRET — signs the session cookie. Terraform-generated.
resource "google_secret_manager_secret" "cc_session_secret" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = "command-center-session-secret"
  replication {
    auto {}
  }
}

resource "random_password" "cc_session_secret" {
  count   = var.enable_command_center ? 1 : 0
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "cc_session_secret" {
  count       = var.enable_command_center ? 1 : 0
  secret      = google_secret_manager_secret.cc_session_secret[0].id
  secret_data = random_password.cc_session_secret[0].result
}

# GOOGLE_CLIENT_SECRET — issued by Google for the command-center OAuth client
# (a NEW client, separate from plant-log's). Placeholder seeded so "latest"
# resolves on first apply; Tyler adds the real value out-of-band.
resource "google_secret_manager_secret" "cc_google_client_secret" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = "command-center-google-client-secret"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "cc_google_client_secret_placeholder" {
  count       = var.enable_command_center ? 1 : 0
  secret      = google_secret_manager_secret.cc_google_client_secret[0].id
  secret_data = "SET-REAL-VALUE-OUT-OF-BAND"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# GITHUB_TOKEN — the least-privilege GitHub merge token (decision #21). The
# service uses ONLY the PR-merge endpoint (command_center/github.py). Terraform
# provisions the container + IAM; Tyler creates a fine-grained PAT scoped to
# merge/contents on exactly the two repos and adds it as a new version. See the
# PR "Tyler-only steps" for the exact scopes. A placeholder is seeded so the
# service starts; with a placeholder token the merge endpoint degrades cleanly
# (503), it does not crash (command_center/github.py).
resource "google_secret_manager_secret" "cc_github_token" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = "command-center-github-token"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "cc_github_token_placeholder" {
  count       = var.enable_command_center ? 1 : 0
  secret      = google_secret_manager_secret.cc_github_token[0].id
  secret_data = "SET-REAL-VALUE-OUT-OF-BAND"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# DATABASE_URL — connection string for the platform state store. Placeholder
# until the state store lives on Cloud SQL (Phase 3); the real value is set
# out-of-band then. Kept as a secret (it carries a DB password) and read by
# reference, never in the repo.
resource "google_secret_manager_secret" "cc_database_url" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = "command-center-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "cc_database_url_placeholder" {
  count       = var.enable_command_center ? 1 : 0
  secret      = google_secret_manager_secret.cc_database_url[0].id
  secret_data = "SET-REAL-VALUE-OUT-OF-BAND"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# --- Per-secret IAM: the runtime SA reads only these four secrets -------------
resource "google_secret_manager_secret_iam_member" "cc_session_secret" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = google_secret_manager_secret.cc_session_secret[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.command_center_run[0].email}"
}

resource "google_secret_manager_secret_iam_member" "cc_google_client_secret" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = google_secret_manager_secret.cc_google_client_secret[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.command_center_run[0].email}"
}

resource "google_secret_manager_secret_iam_member" "cc_github_token" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = google_secret_manager_secret.cc_github_token[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.command_center_run[0].email}"
}

resource "google_secret_manager_secret_iam_member" "cc_database_url" {
  count     = var.enable_command_center ? 1 : 0
  secret_id = google_secret_manager_secret.cc_database_url[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.command_center_run[0].email}"
}

# --- The gated service --------------------------------------------------------
resource "google_cloud_run_v2_service" "command_center" {
  count    = var.enable_command_center ? 1 : 0
  name     = "command-center"
  location = var.region

  # Stateless service (all state is in Postgres); nothing here is destroy-worthy.
  deletion_protection = false

  # INGRESS LOCK. Only traffic from an internal/Cloud-Load-Balancing path may
  # reach the service; direct *.run.app hits from the internet are refused at the
  # edge. Combined with the deliberate ABSENCE of an allUsers run.invoker binding
  # (see header), the service is not openly invokable — closing the gap the PR #28
  # security review flagged and honouring "do NOT inherit the placeholder's
  # allUsers" (platform risk #3). Reachability is provided by the IAP-fronted
  # external HTTPS load balancer proposed in the PR.
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.command_center_run[0].email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.command_center_image

      ports {
        container_port = 8080
      }

      # --- Non-secret runtime config (plain env) ---
      env {
        name  = "SESSION_HTTPS_ONLY"
        value = "true"
      }

      # Tyler only (decision #17). Comma-separated in code; a single address here.
      env {
        name  = "ALLOWED_EMAILS"
        value = var.cc_allowed_emails
      }

      # REQUIRED and load-bearing: a non-empty GOOGLE_CLIENT_ID both wires up real
      # OIDC sign-in AND arms the backend's fail-closed guard — with it set, a
      # stray DEV_AUTH=1 makes the app refuse to start (command_center/config.py).
      # cc_google_client_id defaults to "" ONLY so the pipeline resolves while this
      # service is gated OFF; the var's validation rejects a blank the instant
      # enable_command_center flips to true, so a blank value can never ship live.
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.cc_google_client_id
      }

      env {
        name  = "GOOGLE_REDIRECT_URI"
        value = var.cc_google_redirect_uri
      }

      # NOTE: DEV_AUTH is intentionally NEVER set here. The dev-login backdoor and
      # the docs/openapi surfaces stay fenced off in this service (PRD §6). Its
      # absence + the GOOGLE_CLIENT_ID guard above are belt-and-suspenders.

      # --- Secrets, read from Secret Manager at runtime via the runtime SA ---
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.cc_session_secret[0].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.cc_google_client_secret[0].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.cc_github_token[0].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.cc_database_url[0].secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 3
        failure_threshold     = 30
      }

      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        period_seconds = 30
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.platform.connection_name]
      }
    }
  }

  # CI/`gcloud run deploy` owns the running image after the first apply; Terraform
  # must not revert a shipped revision back to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  # The runtime SA must be able to read the secrets and the seed versions must
  # exist before the first revision starts.
  depends_on = [
    google_secret_manager_secret_iam_member.cc_session_secret,
    google_secret_manager_secret_iam_member.cc_google_client_secret,
    google_secret_manager_secret_iam_member.cc_github_token,
    google_secret_manager_secret_iam_member.cc_database_url,
    google_secret_manager_secret_version.cc_session_secret,
    google_secret_manager_secret_version.cc_google_client_secret_placeholder,
    google_secret_manager_secret_version.cc_github_token_placeholder,
    google_secret_manager_secret_version.cc_database_url_placeholder,
  ]
}

# DELIBERATELY ABSENT: there is NO google_cloud_run_v2_service_iam_member granting
# roles/run.invoker to allUsers (or anyone) on this service. That absence is the
# point (platform risk #3). Invoke permission is granted narrowly to the load
# balancer / IAP service agent when the fronting lands — see the PR proposal.
