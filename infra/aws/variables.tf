variable "aws_region" {
  type        = string
  description = "AWS region. Keep the ACM certificate in this region."
}
variable "environment" {
  type    = string
  default = "production"
}
variable "project_name" {
  type    = string
  default = "mindmesh"
}
variable "web_domain" {
  type        = string
  description = "Public website hostname, for example app.example.com."
}
variable "api_domain" {
  type        = string
  description = "Public API hostname, for example api.example.com."
}
variable "acm_certificate_arn" {
  type        = string
  description = "Issued ACM certificate covering both web_domain and api_domain."
}
variable "deploy_services" {
  type        = bool
  default     = false
  description = "Set true only after images are pushed to ECR and runtime secrets are populated."
}
variable "image_tag" {
  type    = string
  default = "prod"
}
variable "api_desired_count" {
  type    = number
  default = 2
}
variable "api_min_count" {
  type    = number
  default = 2
  validation {
    condition     = var.api_min_count >= 2 && var.api_min_count <= var.api_max_count
    error_message = "api_min_count must be at least 2 and no greater than api_max_count."
  }
}
variable "api_max_count" {
  type    = number
  default = 6
}
variable "worker_desired_count" {
  type    = number
  default = 1
}
variable "api_cpu" {
  type    = number
  default = 1024
}
variable "api_memory" {
  type    = number
  default = 3072
}
variable "worker_cpu" {
  type    = number
  default = 2048
}
variable "worker_memory" {
  type    = number
  default = 8192
}
variable "worker_ephemeral_storage_gib" {
  type    = number
  default = 50
}
variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}
variable "redis_engine_version" {
  type    = string
  default = "7.1"
}
variable "waf_rate_limit_per_5m" {
  type    = number
  default = 2000
}
variable "alert_email" {
  type        = string
  default     = ""
  description = "Optional email for CloudWatch alarm notifications; subscription must be confirmed."
}
variable "supabase_storage_bucket" {
  type    = string
  default = "mindmesh-private"
}
variable "qdrant_url" {
  type        = string
  description = "HTTPS endpoint of the hosted Qdrant cluster."
  validation {
    condition     = can(regex("^https://", var.qdrant_url))
    error_message = "qdrant_url must use HTTPS."
  }
}
variable "qdrant_collection" {
  type        = string
  default     = "mindmesh_gemini_v1"
  description = "Use a fresh collection for the chosen embedding model; do not point at local/different-model vectors."
}
variable "llm_provider" {
  type    = string
  default = "groq"
  validation {
    condition     = contains(["groq", "xai"], var.llm_provider)
    error_message = "llm_provider must be groq or xai."
  }
}
variable "llm_model" {
  type    = string
  default = "openai/gpt-oss-20b"
}
variable "llm_fallback_provider" {
  type        = string
  default     = ""
  description = "Optional independent provider for Groq 429 and transient outage failover. Leave empty to disable."
  validation {
    condition     = contains(["", "xai"], var.llm_fallback_provider)
    error_message = "llm_fallback_provider must be empty or xai."
  }
}
variable "xai_fallback_model" {
  type        = string
  default     = ""
  description = "Required XAI model ID when llm_fallback_provider is xai."
}
variable "enable_groq_secondary" {
  type        = bool
  default     = false
  description = "Inject GROQ_API_KEY_SECONDARY from the backend Secrets Manager JSON when true."
}
variable "embedding_model" {
  type    = string
  default = "gemini-embedding-2"
}
variable "embedding_dim" {
  type    = number
  default = 768
  validation {
    condition     = var.embedding_dim >= 128 && var.embedding_dim <= 3072
    error_message = "embedding_dim must be between 128 and 3072 for Gemini embeddings."
  }
}
