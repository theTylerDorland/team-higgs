# -----------------------------------------------------------------------------
# team-higgs command center — day-zero address bridge (THROWAWAY placeholder).
#
# WHY: reserve the command-center address (higgs.tylerdorland.com) and warm its
# Google-managed TLS cert NOW, before the real app exists, so front-end/OAuth/DNS
# wiring can proceed against a stable, HTTPS origin.
#
# WHAT THIS IS: a minimal, disposable placeholder Cloud Run service whose ONLY
# jobs are to hold the higgs subdomain mapping and warm the cert. It serves a
# public hello page and nothing else — no Cloud SQL, no secrets, no runtime env.
#
# WHAT THIS IS NOT: this is NOT the command center. The REAL command center will
# be built as its OWN gated service — its own project, identity, and auth. It
# will NOT reuse this service and must NOT inherit the allUsers -> run.invoker
# binding below. At command-center cutover, THIS placeholder service and its
# public binding are RETIRED/REPLACED with authenticated (or IAP) ingress.
# Tracked as platform risk #3 ("Command-center service must not inherit
# placeholder's allUsers public invoke").
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "higgs_command" {
  name     = "higgs-command"
  location = var.region

  # Stateless, disposable placeholder; nothing here is worth destroy-protecting,
  # and it is meant to be retired at command-center cutover (see header).
  deletion_protection = false

  template {
    # No service_account: the placeholder needs no GCP identity (no Secret
    # Manager, no Cloud SQL). The real command center is a SEPARATE service and
    # will attach its own least-privilege SA — not this one.

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      # Public hello placeholder. It listens on the injected PORT, so the Cloud
      # Run v2 default container port suffices — no ports block needed.
      image = var.higgs_command_image
    }
  }

  # ignore_changes lets the placeholder's holding image be swapped out-of-band
  # (e.g. `gcloud run deploy` of a different hello/holding page) without
  # Terraform reverting it. It does NOT mean the real command center deploys
  # here — that is a separate, gated service (see header; platform risk #3).
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# Public invoke: allUsers may INVOKE (reach the service). Safe ONLY because the
# placeholder serves a static hello page with no data and no identity. This
# binding is STICKY and must not outlive the placeholder: the REAL command center
# is a SEPARATE, gated service that must NOT inherit it. At cutover, retire this
# binding together with the placeholder and front the real service with
# authenticated (or IAP) ingress. Tracked as platform risk #3 ("Command-center
# service must not inherit placeholder's allUsers public invoke").
resource "google_cloud_run_v2_service_iam_member" "higgs_command_public_invoke" {
  name     = google_cloud_run_v2_service.higgs_command.name
  location = google_cloud_run_v2_service.higgs_command.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom-domain mapping: binds higgs.tylerdorland.com to the higgs-command
# service (referenced by name via spec.route_name, which also gives Terraform an
# implicit dependency on the service). certificate_mode = AUTOMATIC has Cloud Run
# provision and renew a Google-managed TLS cert once DNS resolves — no cert
# resource needed. The parent domain is already Search-Console-verified for
# tyler@tylerdorland.com, so the mapping applies cleanly.
#
# ONLY the higgs subdomain is mapped. The apex (tylerdorland.com) and www are
# Tyler's Squarespace site and are deliberately left untouched.
#
# After apply, the mapping emits a CNAME (host `higgs` -> ghs.googlehosted.com.)
# that Tyler adds at Squarespace DNS; the cert then auto-provisions. See the PR
# go-live checklist.
resource "google_cloud_run_domain_mapping" "higgs_command" {
  location = var.region
  name     = "higgs.tylerdorland.com"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name       = google_cloud_run_v2_service.higgs_command.name
    certificate_mode = "AUTOMATIC"
  }
}
