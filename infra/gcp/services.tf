locals {
  backend_environment = [
    { name = "APP_NAME", value = "MindMesh" },
    { name = "ENVIRONMENT", value = "production" },
    { name = "API_PREFIX", value = "/api" },
    { name = "CORS_ORIGINS", value = "https://${var.web_domain}" },
    { name = "MINDMESH_EXECUTION_MODE", value = "cloud" },
    { name = "AUTH_ENABLED", value = "true" },
    { name = "SUPABASE_STORAGE_BUCKET", value = var.supabase_storage_bucket },
    { name = "SUPABASE_DB_POOL_MAX_SIZE", value = "3" },
    { name = "SUPABASE_DB_POOL_TIMEOUT_SECONDS", value = "10" },
    { name = "QDRANT_URL", value = var.qdrant_url },
    { name = "QDRANT_COLLECTION", value = var.qdrant_collection },
    { name = "LLM_PROVIDER", value = var.llm_provider },
    { name = "GROQ_MODEL", value = var.llm_model },
    { name = "XAI_MODEL", value = var.llm_model },
    { name = "EMBEDDING_PROVIDER", value = "gemini" },
    { name = "EMBEDDING_MODEL", value = var.embedding_model },
    { name = "EMBEDDING_DIM", value = tostring(var.embedding_dim) },
    { name = "SSRF_BLOCK_PRIVATE", value = "true" },
    { name = "CRAWL4AI_HEADLESS", value = "true" },
    { name = "CRAWL4AI_CACHE_MODE", value = "bypass" },
    { name = "RATE_LIMIT_ENABLED", value = "true" },
    { name = "TRUST_PROXY", value = "true" },
    { name = "TRUST_PROXY_XFF_INDEX", value = "second-last" },
    { name = "PAYMENTS_ENABLED", value = "false" },
    { name = "MAX_CONCURRENT_HEAVY_TASKS", value = "2" },
    # Cloud Run's HTTP/1 request cap is 32 MiB; leave room for multipart framing.
    { name = "MAX_MULTIPART_BODY_SIZE", value = "31457280" },
    { name = "MAX_UPLOAD_SIZE", value = "29360128" },
    { name = "PDF_MAX_FILE_SIZE", value = "29360128" },
    { name = "SSE_MAX_WAIT_SECONDS", value = "3500" },
  ]
  gcp_environment = [
    { name = "GCP_PROJECT_ID", value = var.project_id },
    { name = "GCP_REGION", value = var.region },
    { name = "CLOUD_TASKS_QUEUE", value = google_cloud_tasks_queue.jobs.name },
    { name = "CLOUD_TASKS_SERVICE_ACCOUNT", value = google_service_account.tasks_invoker.email },
    { name = "CLOUD_RUN_JOB_NAME", value = "mindmesh-worker" },
  ]
  redis_environment = [
    { name = "REDIS_URL", value = "rediss://${google_redis_instance.cache.host}:6378" },
    { name = "REDIS_SSL_CA_CERTS", value = "/var/run/secrets/redis/ca.pem" },
  ]
}

resource "google_cloud_run_v2_service" "api" {
  count               = var.deploy_services ? 1 : 0
  project             = var.project_id
  name                = "mindmesh-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = true
  labels              = { application = "mindmesh", environment = "production" }
  template {
    service_account                  = google_service_account.api.email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = 40
    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.app.name
        subnetwork = google_compute_subnetwork.run.name
      }
    }
    volumes {
      name = "redis-ca"
      secret {
        secret = google_secret_manager_secret.runtime["REDIS_SERVER_CA"].secret_id
        items {
          path    = "ca.pem"
          version = "latest"
        }
      }
    }
    containers {
      name  = "api"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}/api:${var.image_tag}"
      ports { container_port = 8000 }
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
      dynamic "env" {
        for_each = concat(local.backend_environment, local.redis_environment, local.gcp_environment, [
          { name = "JOB_BACKEND", value = "gcp" },
          { name = "CLOUD_TASKS_DISPATCHER_URL", value = google_cloud_run_v2_service.dispatcher[0].uri },
        ])
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
      dynamic "env" {
        for_each = local.public_runtime_secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
      env {
        name = "CLOUD_TASKS_DISPATCH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["CLOUD_TASKS_DISPATCH_SECRET"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "REDIS_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["REDIS_AUTH_STRING"].secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "redis-ca"
        mount_path = "/var/run/secrets/redis"
      }
    }
  }
  lifecycle { ignore_changes = [template[0].containers[0].image] }
  depends_on = [google_secret_manager_secret_iam_member.runtime_access]
}

resource "google_cloud_run_v2_service" "web" {
  count               = var.deploy_services ? 1 : 0
  project             = var.project_id
  name                = "mindmesh-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = true
  labels              = { application = "mindmesh", environment = "production" }
  template {
    service_account                  = google_service_account.web.email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = 80
    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }
    containers {
      name  = "web"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}/web:${var.image_tag}"
      ports { container_port = 3000 }
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      env {
        name  = "NODE_ENV"
        value = "production"
      }
      env {
        name  = "PORT"
        value = "3000"
      }
      env {
        name  = "HOSTNAME"
        value = "0.0.0.0"
      }
    }
  }
  lifecycle { ignore_changes = [template[0].containers[0].image] }
}

resource "google_cloud_run_v2_service" "dispatcher" {
  count               = var.deploy_services ? 1 : 0
  project             = var.project_id
  name                = "mindmesh-dispatcher"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = true
  labels              = { application = "mindmesh", environment = "production" }
  template {
    service_account                  = google_service_account.dispatcher.email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = 10
    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.app.name
        subnetwork = google_compute_subnetwork.run.name
      }
    }
    volumes {
      name = "redis-ca"
      secret {
        secret = google_secret_manager_secret.runtime["REDIS_SERVER_CA"].secret_id
        items {
          path    = "ca.pem"
          version = "latest"
        }
      }
    }
    containers {
      name    = "dispatcher"
      image   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}/api:${var.image_tag}"
      command = ["uvicorn"]
      args    = ["app.dispatcher:app", "--host", "0.0.0.0", "--port", "8000"]
      ports { container_port = 8000 }
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      dynamic "env" {
        for_each = concat(local.backend_environment, local.redis_environment, local.gcp_environment, [
          # The dispatcher reads durable Postgres jobs and launches Cloud Run Jobs;
          # only the public API creates Cloud Tasks, avoiding a self-URL dependency.
          { name = "JOB_BACKEND", value = "postgres" },
        ])
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
      dynamic "env" {
        for_each = local.public_runtime_secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
      env {
        name = "CLOUD_TASKS_DISPATCH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["CLOUD_TASKS_DISPATCH_SECRET"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "REDIS_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["REDIS_AUTH_STRING"].secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "redis-ca"
        mount_path = "/var/run/secrets/redis"
      }
    }
  }
  lifecycle { ignore_changes = [template[0].containers[0].image] }
  depends_on = [google_secret_manager_secret_iam_member.runtime_access]
}

resource "google_cloud_run_v2_job" "worker" {
  count               = var.deploy_services ? 1 : 0
  project             = var.project_id
  name                = "mindmesh-worker"
  location            = var.region
  deletion_protection = true
  labels              = { application = "mindmesh", environment = "production" }
  template {
    parallelism = 1
    task_count  = 1
    template {
      service_account = google_service_account.worker.email
      timeout         = "3600s"
      max_retries     = 0
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.app.name
          subnetwork = google_compute_subnetwork.run.name
        }
      }
      volumes {
        name = "redis-ca"
        secret {
          secret = google_secret_manager_secret.runtime["REDIS_SERVER_CA"].secret_id
          items {
            path    = "ca.pem"
            version = "latest"
          }
        }
      }
      containers {
        name    = "worker"
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}/worker:${var.image_tag}"
        command = ["python"]
        args    = ["-m", "app.gcp_worker"]
        resources {
          limits = { cpu = "2", memory = "8Gi" }
        }
        dynamic "env" {
          for_each = concat(local.backend_environment, local.redis_environment, local.gcp_environment, [
            { name = "JOB_BACKEND", value = "gcp" },
            { name = "WORKER_PROCESS", value = "true" },
            { name = "CLOUD_TASKS_DISPATCHER_URL", value = google_cloud_run_v2_service.dispatcher[0].uri },
          ])
          content {
            name  = env.value.name
            value = env.value.value
          }
        }
        dynamic "env" {
          for_each = local.public_runtime_secrets
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.runtime[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
        env {
          name = "CLOUD_TASKS_DISPATCH_SECRET"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime["CLOUD_TASKS_DISPATCH_SECRET"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "REDIS_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime["REDIS_AUTH_STRING"].secret_id
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "redis-ca"
          mount_path = "/var/run/secrets/redis"
        }
      }
    }
  }
  lifecycle { ignore_changes = [template[0].template[0].containers[0].image] }
  depends_on = [google_secret_manager_secret_iam_member.runtime_access]
}
