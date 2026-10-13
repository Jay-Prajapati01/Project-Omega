resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "mindmesh-api"
  display_name = "MindMesh public API runtime"
}

resource "google_service_account" "web" {
  project      = var.project_id
  account_id   = "mindmesh-web"
  display_name = "MindMesh public website runtime (no secret access)"
}

resource "google_service_account" "dispatcher" {
  project      = var.project_id
  account_id   = "mindmesh-dispatcher"
  display_name = "MindMesh private Cloud Tasks dispatcher"
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "mindmesh-worker"
  display_name = "MindMesh Cloud Run Job worker"
}

resource "google_service_account" "tasks_invoker" {
  project      = var.project_id
  account_id   = "mindmesh-tasks-invoker"
  display_name = "Identity Cloud Tasks uses to invoke the private dispatcher"
}

resource "google_service_account" "github_deploy" {
  project      = var.project_id
  account_id   = "mindmesh-github-deploy"
  display_name = "GitHub Actions OIDC build and deploy identity"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "mindmesh-github"
  display_name              = "MindMesh GitHub Actions"
  description               = "Federated deployment identity restricted to the production repository branch."
  disabled                  = false
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "project-omega-main"
  display_name                       = "Project Omega main branch"
  description                        = "GitHub Actions OIDC; repository and ref are checked in the provider condition."
  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository"    = "assertion.repository"
    "attribute.ref"           = "assertion.ref"
    "attribute.repository_id" = "assertion.repository_id"
  }
  attribute_condition = "assertion.repository == 'Jay-Prajapati01/Project-Omega' && assertion.ref == 'refs/heads/main'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/Jay-Prajapati01/Project-Omega"
}

resource "google_project_iam_member" "github_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_project_iam_member" "github_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_service_account_iam_member" "github_act_as" {
  for_each           = toset([google_service_account.api.email, google_service_account.dispatcher.email, google_service_account.worker.email, google_service_account.web.email])
  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_cloud_run_v2_job_iam_member" "dispatcher_job_executor" {
  count    = var.deploy_services ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.worker[0].name
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.dispatcher.email}"
}

resource "google_service_account_iam_member" "api_tasks_act_as" {
  service_account_id = google_service_account.tasks_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_tasks_queue_iam_member" "api_enqueue" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_tasks_queue.jobs.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each = {
    for pair in setproduct(
      [google_service_account.api.email, google_service_account.dispatcher.email, google_service_account.worker.email],
      [for secret in google_secret_manager_secret.runtime : secret.secret_id]
    ) : "${pair[0]}:${pair[1]}" => pair
  }
  project   = var.project_id
  secret_id = each.value[1]
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value[0]}"
}

resource "google_cloud_run_v2_service_iam_member" "dispatcher_tasks_invoker" {
  count    = var.deploy_services ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.dispatcher[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  count    = var.deploy_services ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  count    = var.deploy_services ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
