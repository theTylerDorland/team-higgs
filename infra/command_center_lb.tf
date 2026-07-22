# =============================================================================
# Command-center reachability fronting — Option A (decision #24, accepted):
# an EXTERNAL HTTPS Application Load Balancer + serverless NEG in front of the
# gated `command-center` Cloud Run service (command_center.tf), gated by
# Identity-Aware Proxy (IAP, allowlist = Tyler only), with the app's own Google
# OIDC left ON behind it as defence-in-depth. Closes the reachability half of
# platform risk #3: the service that can MERGE PRs must be reachable ONLY through
# IAP, never openly invokable.
#
# WHY A LOAD BALANCER AT ALL (for the backend engineer reading this in review):
# command_center.tf locks the service two ways at once — ingress =
# INTERNAL_LOAD_BALANCER (the edge refuses direct *.run.app hits) and NO
# run.invoker binding of any kind (no allUsers, no one). That is deliberately
# UNREACHABLE. A browser cannot present a GCP IAM token, so we cannot simply add
# a user to run.invoker and call it reachable. The fix is to put a Google-managed
# front door in the path that (a) authenticates the human at the edge (IAP), and
# (b) presents an *authorized machine identity* to Cloud Run on their behalf. The
# chain below is that front door.
#
# THE REQUEST PATH, edge to app:
#   browser ─HTTPS─▶ global forwarding rule (:443 on a static anycast IP)
#            ─▶ target HTTPS proxy (terminates TLS with the managed cert)
#            ─▶ URL map (routing; here: everything ─▶ the one backend)
#            ─▶ backend service (IAP ENABLED — the auth gate)
#            ─▶ serverless NEG ─▶ Cloud Run `command-center`
# IAP sits on the backend service: an unauthenticated request is bounced to
# Google sign-in; only a signed-in identity holding roles/iap.httpsResourceAccessor
# (granted to Tyler ONLY, below) is let through. IAP then invokes Cloud Run as the
# IAP service agent, which is the ONLY principal granted run.invoker on the
# service — so the app is reachable exclusively along this path.
#
# GATING: every resource here is behind `count = var.enable_command_center ? 1 : 0`,
# matching command_center.tf. enable_command_center is currently true
# (ci.auto.tfvars, task #37), so this whole graph is a pure ADD on the next
# apply-on-merge — zero destroys (none of it is in state yet).
#
# WHAT THIS PR DOES NOT DO (sequenced later, see infra/command-center-cutover.md):
#   * It does NOT touch DNS. higgs.tylerdorland.com still points at the
#     `higgs-command` placeholder. The managed cert below stays PROVISIONING until
#     DNS is later cut over to this LB's IP — expected and harmless.
#   * It does NOT retire the placeholder (higgs_command.tf) or its allUsers bind.
#   * It does NOT change command_center.tf (ingress stays INTERNAL_LOAD_BALANCER;
#     the absent-allUsers stance is untouched). Invoke is granted ONLY to the IAP
#     service agent, resource-scoped to the command-center service.
#
# IAP OAuth client — the "Google-managed client" path (see PR "IAP-brand
# decision"): the iap{} block below sets enabled=true and supplies NO
# oauth2_client_id / oauth2_client_secret. IAP then provisions and rotates its own
# Google-managed OAuth client. This is deliberate: (1) it puts ZERO secret material
# anywhere — not in the repo, not in tfvars, not in Terraform state; (2) it sidesteps
# the project's OAuth-consent-screen brand, which is almost certainly type EXTERNAL
# (plant-log signs in consumer Gmail accounts that are NOT in the tylerdorland.com
# Workspace org), and an EXTERNAL brand blocks the google_iap_brand/google_iap_client
# Terraform path (those require an INTERNAL, API-created brand; a project has exactly
# one brand). Fallback if the managed client proves unavailable at apply is a
# console-created IAP OAuth client wired via a new var + Secret Manager secret —
# fully documented in the PR. NOTE: schema/plan-validated here, not apply-verified
# (apply runs only on merge).
# =============================================================================

# Project number backs the IAP service agent member string below.
data "google_project" "this" {}

# --- APIs this fronting needs (were NOT enabled on the project) ---------------
# Compute Engine API backs every LB resource (addresses, certs, NEGs, backend
# services, proxies, forwarding rules); the IAP API backs the auth gate and
# provisions the IAP service agent. disable_on_destroy=false: tearing down this
# config must never disable an API underneath other live resources — API-disable
# is a deliberate out-of-band action, mirroring google_project_service.dns.
resource "google_project_service" "compute" {
  count              = var.enable_command_center ? 1 : 0
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iap" {
  count              = var.enable_command_center ? 1 : 0
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

# --- Global static anycast IP (the LB frontend) ------------------------------
# The stable address DNS will later point higgs.tylerdorland.com at (A record).
# Global (not regional) because this is a global external Application LB.
resource "google_compute_global_address" "command_center" {
  count      = var.enable_command_center ? 1 : 0
  name       = "command-center-lb-ip"
  ip_version = "IPV4"

  depends_on = [
    google_project_service.compute,
    time_sleep.cc_lb_iam_propagation,
  ]
}

# --- Google-managed TLS certificate for the command-center host --------------
# Google provisions and auto-renews the cert. It only goes ACTIVE once DNS for
# the domain resolves to this LB's IP — which is a LATER cutover step, so this
# cert stays PROVISIONING after this PR applies. That is expected and blocks
# nothing else; HTTPS goes live at the DNS cutover (runbook step 4).
resource "google_compute_managed_ssl_certificate" "command_center" {
  count = var.enable_command_center ? 1 : 0
  name  = "command-center-cert"

  managed {
    domains = ["higgs.tylerdorland.com"]
  }

  depends_on = [google_project_service.compute]
}

# --- Serverless NEG -> Cloud Run ---------------------------------------------
# A serverless Network Endpoint Group is the LB's pointer at a Cloud Run service
# (no IPs/health checks — the "endpoint" is the managed service). Regional,
# co-located with the service. Referencing command_center[0] ties this to the
# same gate; indices align because both use the same count expression.
resource "google_compute_region_network_endpoint_group" "command_center" {
  count                 = var.enable_command_center ? 1 : 0
  name                  = "command-center-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.command_center[0].name
  }

  depends_on = [google_project_service.compute]
}

# --- Backend service (THE AUTH GATE) -----------------------------------------
# Global backend service fronting the serverless NEG. Serverless NEG backends
# take NO health check (the managed service reports its own health), so none is
# attached. load_balancing_scheme EXTERNAL_MANAGED = the global external
# Application Load Balancer.
#
# iap{ enabled = true } with NO client id/secret => IAP uses its Google-managed
# OAuth client (see file header). This is the gate: IAP authenticates the browser
# at the edge and enforces roles/iap.httpsResourceAccessor (Tyler only, below).
resource "google_compute_backend_service" "command_center" {
  count                 = var.enable_command_center ? 1 : 0
  name                  = "command-center-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"

  backend {
    group = google_compute_region_network_endpoint_group.command_center[0].id
  }

  iap {
    enabled = true
  }

  depends_on = [
    google_project_service.compute,
    google_project_service.iap,
  ]
}

# --- URL map / target HTTPS proxy / forwarding rule --------------------------
# URL map: all paths -> the one backend (single-service app, no path routing).
resource "google_compute_url_map" "command_center" {
  count           = var.enable_command_center ? 1 : 0
  name            = "command-center-urlmap"
  default_service = google_compute_backend_service.command_center[0].id
}

# Target HTTPS proxy: terminates TLS with the managed cert, hands off to the map.
resource "google_compute_target_https_proxy" "command_center" {
  count            = var.enable_command_center ? 1 : 0
  name             = "command-center-https-proxy"
  url_map          = google_compute_url_map.command_center[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.command_center[0].id]
}

# Global forwarding rule: binds the static IP :443 to the HTTPS proxy. Scheme
# must match the backend service (EXTERNAL_MANAGED). This is the resource that
# actually makes the LB answer on the internet.
resource "google_compute_global_forwarding_rule" "command_center" {
  count                 = var.enable_command_center ? 1 : 0
  name                  = "command-center-https"
  target                = google_compute_target_https_proxy.command_center[0].id
  ip_address            = google_compute_global_address.command_center[0].address
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- IAP service agent, provisioned EXPLICITLY (cold-apply race fix) ----------
# The IAP service agent (service-<PROJECT_NUMBER>@gcp-sa-iap.iam.gserviceaccount.com)
# is NOT created synchronously when the IAP API is enabled. Enabling the API
# (google_project_service.iap) kicks off agent provisioning ASYNCHRONOUSLY; on a
# cold apply the agent does not exist yet when the invoker binding below tries to
# reference it, and Cloud Run setIamPolicy rejects a non-existent principal with:
#   Error 400: Service account service-<N>@gcp-sa-iap.iam.gserviceaccount.com does not exist.
# This is exactly what failed task #38's apply-on-merge twice; depends_on the API
# alone is insufficient because the API being ENABLED is not the agent being
# PROVISIONED. google_project_service_identity calls serviceusage
# generateServiceIdentity, which creates the agent deterministically and returns
# only once it exists — turning an async race into an ordered dependency.
#
# IDEMPOTENT / NO-OP on current prod: generateServiceIdentity is safe to call when
# the agent already exists (Higgs created it by hand to unblock #38). This resource
# is not yet in state, so a re-apply CREATES it in state by adopting the existing
# agent — zero effect on the live agent, and (see the invoker binding) zero churn
# of the existing run.invoker binding. beta-only resource (provider = google-beta).
resource "google_project_service_identity" "iap" {
  count    = var.enable_command_center ? 1 : 0
  provider = google-beta
  service  = "iap.googleapis.com"

  depends_on = [google_project_service.iap]
}

# --- Narrow invoke: IAP service agent ONLY, on the command-center service -----
# This is the counterpart to command_center.tf's DELIBERATELY-ABSENT allUsers
# binding. When IAP forwards an authenticated request through a serverless NEG to
# a Cloud Run service that requires authentication, it invokes as the IAP service
# agent: service-<PROJECT_NUMBER>@gcp-sa-iap.iam.gserviceaccount.com. That agent —
# and NOTHING else — is granted run.invoker, resource-scoped to command-center.
# NEVER allUsers (platform risk #3).
#
# ORDERING (the fix): depends_on the google_project_service_identity.iap resource
# above, which guarantees the agent EXISTS before this binding is applied. The
# member string is left byte-for-byte identical (built from the project number,
# known at plan time) precisely so this is a NO-OP against the existing binding in
# prod: switching to a reference on the identity's computed .email would make member
# "known after apply" during the apply that creates the identity, and since member
# is ForceNew that would replace the live binding — the opposite of what we want.
resource "google_cloud_run_v2_service_iam_member" "command_center_iap_invoker" {
  count    = var.enable_command_center ? 1 : 0
  project  = google_cloud_run_v2_service.command_center[0].project
  location = google_cloud_run_v2_service.command_center[0].location
  name     = google_cloud_run_v2_service.command_center[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"

  depends_on = [google_project_service_identity.iap]
}

# --- IAP allowlist: Tyler only ------------------------------------------------
# roles/iap.httpsResourceAccessor on THIS backend service's IAP resource is what
# lets an authenticated identity actually pass IAP. Granted to Tyler ONLY
# (decision #17), resource-scoped to the command-center backend — not project-wide.
# github-ci needs roles/iap.admin to set this (declared out-of-band + codified in
# ci_iam.tf). If org policy blocks CI from self-granting this at apply, it is a
# one-line Tyler-only step (see PR / runbook) and this resource can be removed.
resource "google_iap_web_backend_service_iam_member" "tyler_access" {
  count               = var.enable_command_center ? 1 : 0
  project             = var.project_id
  web_backend_service = google_compute_backend_service.command_center[0].name
  role                = "roles/iap.httpsResourceAccessor"
  member              = "user:tyler@tylerdorland.com"

  depends_on = [google_project_service.iap]
}
