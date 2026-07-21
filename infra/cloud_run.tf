# -----------------------------------------------------------------------------
# plant-log Cloud Run service. One service serves both the JSON API and the
# built React SPA (single image, per the PRD). It:
#   * runs as the least-privilege plantlog-run service account,
#   * mounts the Cloud SQL socket so the app reaches Postgres with no network
#     exposure,
#   * pulls DATABASE_URL / SESSION_SECRET / GOOGLE_CLIENT_SECRET from Secret
#     Manager at runtime (never baked into the image or env in the repo),
#   * listens on 8000 and is health-checked at /healthz.
# The container entrypoint runs `alembic upgrade head` before serving, so the
# startup probe is generous enough to cover a first-boot migration.
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "plant_log" {
  name     = "plant-log"
  location = var.region

  # Only reachable via the public Cloud Run URL below; ingress stays at the
  # default (all) because auth is enforced in-app by the Google sign-in gate.
  deletion_protection = false

  template {
    service_account = google_service_account.plantlog_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.plantlog_image

      ports {
        container_port = 8000
      }

      # Non-secret runtime config (plain env).
      env {
        name  = "SESSION_HTTPS_ONLY"
        value = "true"
      }
      env {
        name  = "ALLOWED_EMAILS"
        value = var.allowed_emails
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_client_id
      }
      env {
        name  = "GOOGLE_REDIRECT_URI"
        value = var.google_redirect_uri
      }
      # Empty ⇒ the www→apex 301 redirect is disabled; set to the apex host in
      # tfvars at cutover to activate it (see plant-log backend PR #11).
      env {
        name  = "CANONICAL_HOST"
        value = var.canonical_host
      }
      # NOTE: DEV_AUTH is intentionally never set — the dev-login backdoor must
      # never be enabled in production.

      # Secrets, read from Secret Manager at runtime via the runtime SA.
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.session_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_client_secret.secret_id
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
          port = 8000
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 3
        failure_threshold     = 30 # up to ~5 min for first-boot migrations
      }

      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8000
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

  # CI/`gcloud run deploy` owns the running image after day zero; Terraform must
  # not revert a shipped revision back to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  # Ensure the runtime SA can read the secrets and the seed versions exist
  # before the first revision tries to start.
  depends_on = [
    google_secret_manager_secret_iam_member.database_url,
    google_secret_manager_secret_iam_member.session_secret,
    google_secret_manager_secret_iam_member.google_client_secret,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.session_secret,
    google_secret_manager_secret_version.google_client_secret_placeholder,
  ]
}

# Public URL: the PRD specifies a public service with all routes behind the
# in-app Google auth gate. allUsers may INVOKE (reach the app); the app itself
# rejects unauthenticated/unlisted users. This is deliberate — see README.
resource "google_cloud_run_v2_service_iam_member" "public_invoke" {
  name     = google_cloud_run_v2_service.plant_log.name
  location = google_cloud_run_v2_service.plant_log.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
