# -----------------------------------------------------------------------------
# Secret Manager: plant-log runtime secrets. The Cloud Run service reads these
# at runtime via its own service identity (see cloud_run.tf / iam.tf). Nothing
# secret is stored in the repo, env files, tfvars, or workflow definitions.
#
# Two kinds of secret here:
#   * Terraform-generated (database URL, session key): Terraform owns the value.
#     The generated value lands in Terraform state — accepted, because remote
#     state is a versioned, access-controlled GCS bucket, the same trust
#     boundary as Secret Manager itself. See infra/README.md "Secrets".
#   * Externally-supplied (Google OAuth client secret): Terraform creates the
#     container and seeds a harmless placeholder version so the first apply can
#     succeed; Tyler sets the real value out-of-band (documented in README). The
#     service always reads version = "latest".
# -----------------------------------------------------------------------------

# --- DATABASE_URL (contains the generated DB password) ------------------------
resource "google_secret_manager_secret" "database_url" {
  secret_id = "plantlog-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  # SQLAlchemy/psycopg unix-socket form. Cloud Run mounts the Cloud SQL socket at
  # /cloudsql/<connection_name>; psycopg connects through it, so no host/port is
  # exposed. Password is URL-safe (see random_password override_special).
  secret_data = "postgresql+psycopg://${google_sql_user.plantlog.name}:${random_password.plantlog_db.result}@/plantlog?host=/cloudsql/${google_sql_database_instance.platform.connection_name}"
}

# --- SESSION_SECRET (signs the session cookie) --------------------------------
resource "google_secret_manager_secret" "session_secret" {
  secret_id = "plantlog-session-secret"
  replication {
    auto {}
  }
}

resource "random_password" "session_secret" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "session_secret" {
  secret      = google_secret_manager_secret.session_secret.id
  secret_data = random_password.session_secret.result
}

# --- GOOGLE_CLIENT_SECRET (issued by Google; set out-of-band) -----------------
resource "google_secret_manager_secret" "google_client_secret" {
  secret_id = "plantlog-google-client-secret"
  replication {
    auto {}
  }
}

# Placeholder so version "latest" resolves on the first apply and the Cloud Run
# revision can start. Tyler adds the real value as a NEW version out-of-band
# (see README); "latest" then points at the real value. Terraform keeps owning
# only this placeholder version and will not fight the real one.
resource "google_secret_manager_secret_version" "google_client_secret_placeholder" {
  secret      = google_secret_manager_secret.google_client_secret.id
  secret_data = "SET-REAL-VALUE-OUT-OF-BAND"

  lifecycle {
    ignore_changes = [secret_data]
  }
}
