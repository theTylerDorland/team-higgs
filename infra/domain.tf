# -----------------------------------------------------------------------------
# Custom-domain mappings for the plant-log Cloud Run service.
#
# WHY: the service currently answers on two auto-assigned *.run.app hostnames.
# OAuth `state` is kept in a host-scoped session cookie, so a login begun on one
# host and finished on the other fails with "Invalid OAuth state". Mapping a
# single canonical domain (the apex) onto the service gives login one stable
# origin and removes the cross-host cookie mismatch.
#
# Each google_cloud_run_domain_mapping binds a DNS name to the existing
# `plant-log` service (referenced by name via spec.route_name, which also gives
# Terraform an implicit dependency on the service). Cloud Run provisions and
# renews a Google-managed TLS certificate for the mapped domain automatically —
# no cert resource is declared or needed. `.app` is on the HSTS preload list, so
# HTTPS is mandatory; the managed cert covers it.
#
# After apply, each mapping emits the DNS records Tyler must add at the domain
# registrar (A/AAAA for the apex, CNAME for www) — see infra/README and the PR
# go-live checklist. The mappings apply cleanly before DNS resolves; the managed
# cert only provisions once the records point at Google.
# -----------------------------------------------------------------------------

resource "google_cloud_run_domain_mapping" "apex" {
  location = var.region
  name     = "airportbar.app"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.plant_log.name
  }
}

resource "google_cloud_run_domain_mapping" "www" {
  location = var.region
  name     = "www.airportbar.app"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.plant_log.name
  }
}
