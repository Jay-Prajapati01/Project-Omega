resource "google_compute_security_policy" "public" {
  count       = var.deploy_services ? 1 : 0
  project     = var.project_id
  name        = "mindmesh-production-edge"
  description = "Rate limits and filters common web attacks for public web and API backends."
  type        = "CLOUD_ARMOR"

  rule {
    priority    = 1000
    action      = "deny(403)"
    description = "Block common SQL injection patterns."
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})"
      }
    }
  }

  rule {
    priority    = 2000
    action      = "throttle"
    description = "Bound high-volume requests from one source IP."
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.waf_requests_per_ip_per_minute
        interval_sec = 60
      }
    }
  }

  rule {
    priority    = 2147483647
    action      = "allow"
    description = "Default allow after inspection and rate limiting."
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "web" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-web-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run { service = google_cloud_run_v2_service.web[0].name }
}

resource "google_compute_region_network_endpoint_group" "api" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-api-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run { service = google_cloud_run_v2_service.api[0].name }
}

resource "google_compute_backend_service" "web" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-web-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  timeout_sec           = 3600
  security_policy       = google_compute_security_policy.public[0].id
  log_config {
    enable      = true
    sample_rate = 1.0
  }
  backend { group = google_compute_region_network_endpoint_group.web[0].id }
}

resource "google_compute_backend_service" "api" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-api-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  timeout_sec           = 3600
  security_policy       = google_compute_security_policy.public[0].id
  log_config {
    enable      = true
    sample_rate = 1.0
  }
  backend { group = google_compute_region_network_endpoint_group.api[0].id }
}

resource "google_compute_url_map" "https" {
  count           = var.deploy_services ? 1 : 0
  project         = var.project_id
  name            = "mindmesh-production-https"
  default_service = google_compute_backend_service.web[0].id
  host_rule {
    hosts        = [var.web_domain]
    path_matcher = "web"
  }
  host_rule {
    hosts        = [var.api_domain]
    path_matcher = "api"
  }
  path_matcher {
    name            = "web"
    default_service = google_compute_backend_service.web[0].id
  }
  path_matcher {
    name            = "api"
    default_service = google_compute_backend_service.api[0].id
  }
}

resource "google_compute_url_map" "http_redirect" {
  count   = var.deploy_services ? 1 : 0
  project = var.project_id
  name    = "mindmesh-production-http-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_managed_ssl_certificate" "public" {
  count   = var.deploy_services ? 1 : 0
  project = var.project_id
  name    = "mindmesh-production-cert"
  managed {
    domains = [var.web_domain, var.api_domain]
  }
}

resource "google_compute_global_address" "frontend" {
  count        = var.deploy_services ? 1 : 0
  project      = var.project_id
  name         = "mindmesh-production-ip"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

resource "google_compute_target_https_proxy" "public" {
  count            = var.deploy_services ? 1 : 0
  project          = var.project_id
  name             = "mindmesh-production-https"
  url_map          = google_compute_url_map.https[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.public[0].id]
}

resource "google_compute_global_forwarding_rule" "https" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-production-https"
  ip_address            = google_compute_global_address.frontend[0].address
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.public[0].id
  network_tier          = "PREMIUM"
}

resource "google_compute_target_http_proxy" "redirect" {
  count   = var.deploy_services ? 1 : 0
  project = var.project_id
  name    = "mindmesh-production-http"
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http" {
  count                 = var.deploy_services ? 1 : 0
  project               = var.project_id
  name                  = "mindmesh-production-http"
  ip_address            = google_compute_global_address.frontend[0].address
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.redirect[0].id
  network_tier          = "PREMIUM"
}
