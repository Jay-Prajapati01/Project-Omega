resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.project_name}-${var.environment}"
  description                = "MindMesh shared production rate-limit store"
  engine                     = "redis"
  engine_version             = var.redis_engine_version
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  apply_immediately          = false
  auto_minor_version_upgrade = true
}

resource "aws_secretsmanager_secret" "backend" {
  name                    = "/${var.project_name}/${var.environment}/backend"
  description             = "Runtime credentials for MindMesh API and worker. Populate JSON values before starting ECS services."
  recovery_window_in_days = 30
}

resource "aws_ecr_repository" "images" {
  for_each             = toset(["web", "api", "worker"])
  name                 = "${var.project_name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "images" {
  for_each   = aws_ecr_repository.images
  repository = each.value.name
  policy = jsonencode({ rules = [{ rulePriority = 1, description = "Keep recent release tags", selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }, action = { type = "expire" } }] })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}/api"
  retention_in_days = 30
}
resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name}/web"
  retention_in_days = 30
}
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}/worker"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "secret_read" {
  name = "read-mindmesh-runtime-secrets"
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_secretsmanager_secret.backend.arn] }] })
}
resource "aws_iam_role" "task" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

locals {
  backend_environment = [
    { name = "APP_NAME", value = "MindMesh" },
    { name = "ENVIRONMENT", value = "production" },
    { name = "API_PREFIX", value = "/api" },
    { name = "CORS_ORIGINS", value = local.web_origin },
    { name = "MINDMESH_EXECUTION_MODE", value = "cloud" },
    { name = "AUTH_ENABLED", value = "true" },
    { name = "JOB_BACKEND", value = "postgres" },
    { name = "WORKER_POLL_SECONDS", value = "10" },
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
    # Only the ALB can reach API tasks; ALB appends the observed client IP.
    { name = "TRUST_PROXY", value = "true" },
    { name = "PAYMENTS_ENABLED", value = "false" },
    { name = "MAX_CONCURRENT_HEAVY_TASKS", value = "2" }
  ]
  runtime_secret_names = concat([
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL",
    "QDRANT_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY",
    "BYOK_ENCRYPTION_KEY", "PROMO_HMAC_PEPPER", "OWNER_BOOTSTRAP_USER_ID"
  ], var.enable_groq_secondary ? ["GROQ_API_KEY_SECONDARY"] : [])
  backend_secrets = [for key in local.runtime_secret_names : {
    name      = key
    valueFrom = "${aws_secretsmanager_secret.backend.arn}:${key}::"
  }]
  redis_url = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name = "api", image = "${aws_ecr_repository.images["api"].repository_url}:${var.image_tag}", essential = true,
    portMappings = [{ containerPort = 8000, protocol = "tcp" }],
    environment = concat(local.backend_environment, [{ name = "REDIS_URL", value = local.redis_url }, { name = "WORKER_PROCESS", value = "false" }]),
    secrets = local.backend_secrets,
    healthCheck = { command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)\""], interval = 30, timeout = 5, retries = 3, startPeriod = 120 },
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.api.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "api" } }
  }])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name = "web", image = "${aws_ecr_repository.images["web"].repository_url}:${var.image_tag}", essential = true,
    portMappings = [{ containerPort = 3000, protocol = "tcp" }],
    environment = [{ name = "NODE_ENV", value = "production" }, { name = "PORT", value = "3000" }, { name = "HOSTNAME", value = "0.0.0.0" }],
    healthCheck = { command = ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ || exit 1"], interval = 30, timeout = 5, retries = 3, startPeriod = 60 },
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.web.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "web" } }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  ephemeral_storage { size_in_gib = var.worker_ephemeral_storage_gib }
  container_definitions = jsonencode([{
    name = "worker", image = "${aws_ecr_repository.images["worker"].repository_url}:${var.image_tag}", essential = true,
    environment = concat(local.backend_environment, [{ name = "REDIS_URL", value = local.redis_url }, { name = "WORKER_PROCESS", value = "true" }]),
    secrets = local.backend_secrets,
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.worker.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "worker" } }
  }])
}
