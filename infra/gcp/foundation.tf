locals {
  name = "mindmesh-production"
  apis = toset([
    "artifactregistry.googleapis.com",
    "cloudtasks.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "servicenetworking.googleapis.com",
    "sts.googleapis.com",
  ])
  public_runtime_secrets = setunion(toset([
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL",
    "QDRANT_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY",
    "BYOK_ENCRYPTION_KEY", "PROMO_HMAC_PEPPER", "OWNER_BOOTSTRAP_USER_ID",
  ]), var.enable_groq_secondary ? toset(["GROQ_API_KEY_SECONDARY"]) : toset([]))
  all_runtime_secrets = setunion(local.public_runtime_secrets, toset([
    "CLOUD_TASKS_DISPATCH_SECRET", "REDIS_AUTH_STRING", "REDIS_SERVER_CA",
  ]))
}

resource "google_project_service" "enabled" {
  for_each           = local.apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  project       = var.project_id
  location      = var.region
  repository_id = "mindmesh"
  description   = "MindMesh GCP-only production container images"
  format        = "DOCKER"
  labels        = { application = "mindmesh", environment = "production" }
  depends_on    = [google_project_service.enabled]
}

resource "google_compute_network" "app" {
  project                 = var.project_id
  name                    = "${local.name}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.enabled]
}

resource "google_compute_subnetwork" "run" {
  project                  = var.project_id
  name                     = "${local.name}-run"
  region                   = var.region
  network                  = google_compute_network.app.id
  ip_cidr_range            = "10.70.0.0/24"
  private_ip_google_access = true
}

resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "${local.name}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.app.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.app.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
  depends_on              = [google_project_service.enabled]
}

resource "google_redis_instance" "cache" {
  project                 = var.project_id
  name                    = "${local.name}-redis"
  region                  = var.region
  tier                    = "STANDARD_HA"
  memory_size_gb          = var.memorystore_memory_gb
  redis_version           = "REDIS_7_2"
  display_name            = "MindMesh shared production rate-limit cache"
  authorized_network      = google_compute_network.app.id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  auth_enabled            = true
  labels                  = { application = "mindmesh", environment = "production" }
  depends_on              = [google_service_networking_connection.private_services]
}

resource "google_secret_manager_secret" "runtime" {
  for_each  = local.all_runtime_secrets
  project   = var.project_id
  secret_id = lower(replace(each.value, "_", "-"))
  replication {
    auto {}
  }
  labels = { application = "mindmesh", environment = "production" }
  depends_on = [google_project_service.enabled]
}

resource "random_password" "dispatch" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "dispatch_secret" {
  secret      = google_secret_manager_secret.runtime["CLOUD_TASKS_DISPATCH_SECRET"].id
  secret_data = random_password.dispatch.result
}

resource "google_secret_manager_secret_version" "redis_password" {
  secret      = google_secret_manager_secret.runtime["REDIS_AUTH_STRING"].id
  secret_data = google_redis_instance.cache.auth_string
}

resource "google_secret_manager_secret_version" "redis_ca" {
  secret      = google_secret_manager_secret.runtime["REDIS_SERVER_CA"].id
  secret_data = google_redis_instance.cache.server_ca_certs[0].cert
}

resource "google_secret_manager_secret_version" "owner_bootstrap_disabled" {
  secret      = google_secret_manager_secret.runtime["OWNER_BOOTSTRAP_USER_ID"].id
  secret_data = "disabled"
}

resource "google_cloud_tasks_queue" "jobs" {
  project  = var.project_id
  location = var.region
  name     = "mindmesh-jobs"
  rate_limits {
    max_dispatches_per_second = 2
    max_concurrent_dispatches = var.worker_max_concurrent_executions
  }
  retry_config {
    max_attempts       = 20
    max_backoff        = "3600s"
    max_doublings      = 5
    max_retry_duration = "86400s"
    min_backoff        = "10s"
  }
  depends_on = [google_project_service.enabled]
}
