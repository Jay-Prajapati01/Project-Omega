output "project_id" { value = var.project_id }
output "region" { value = var.region }
output "artifact_registry_repository" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
  description = "GitHub Actions pushes versioned web, api, and worker images here."
}
output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Copy to GitHub Actions variable GCP_WORKLOAD_IDENTITY_PROVIDER."
}
output "github_deploy_service_account" {
  value       = google_service_account.github_deploy.email
  description = "Copy to GitHub Actions variable GCP_DEPLOY_SERVICE_ACCOUNT."
}
output "dispatcher_uri" {
  value       = var.deploy_services ? google_cloud_run_v2_service.dispatcher[0].uri : null
  description = "Internal-only dispatcher URL, used in the backend runtime configuration."
}
output "load_balancer_ip" {
  value       = var.deploy_services ? google_compute_global_address.frontend[0].address : null
  description = "Add A records for both public hostnames after the services have been deployed."
}
output "website_url" { value = "https://${var.web_domain}" }
output "api_url" { value = "https://${var.api_domain}/api" }
output "runtime_secret_names" {
  value       = { for name, secret in google_secret_manager_secret.runtime : name => secret.secret_id }
  description = "Create versions for application secrets in Secret Manager before enabling services."
}
output "redis_private_endpoint" {
  value       = "${google_redis_instance.cache.host}:6378"
  description = "Private TLS endpoint; only Cloud Run VPC-connected workloads can reach it."
}
output "cloud_tasks_queue" { value = google_cloud_tasks_queue.jobs.name }
