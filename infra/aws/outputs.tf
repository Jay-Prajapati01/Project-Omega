output "load_balancer_dns_name" {
  value       = aws_lb.main.dns_name
  description = "Create DNS aliases for both public hostnames to this ALB."
}
output "web_url" { value = "https://${var.web_domain}" }
output "api_url" { value = "https://${var.api_domain}/api" }
output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "ecr_repository_urls" { value = { for name, repo in aws_ecr_repository.images : name => repo.repository_url } }
output "backend_runtime_secret_arn" {
  value       = aws_secretsmanager_secret.backend.arn
  description = "Store the documented JSON runtime settings under this secret before starting ECS services."
}
output "redis_tls_url" {
  value       = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
  description = "Private VPC endpoint; inject into API and worker task definitions only."
  sensitive   = true
}
