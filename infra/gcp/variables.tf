variable "project_id" {
  type        = string
  description = "Dedicated Google Cloud project ID for MindMesh production."
}

variable "region" {
  type        = string
  default     = "asia-south1"
  description = "Primary Cloud Run, Cloud Tasks, Artifact Registry, and Memorystore region."
}

variable "web_domain" {
  type        = string
  description = "Public website hostname, such as app.example.com (hostname only)."
  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+$", var.web_domain))
    error_message = "web_domain must be a hostname without a URL scheme or path."
  }
}

variable "api_domain" {
  type        = string
  description = "Public API hostname, such as api.example.com (hostname only)."
  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+$", var.api_domain)) && var.api_domain != var.web_domain
    error_message = "api_domain must be a distinct hostname without a URL scheme or path."
  }
}

variable "deploy_services" {
  type        = bool
  default     = false
  description = "Enable only after images exist and runtime Secret Manager values are populated."
}

variable "image_tag" {
  type    = string
  default = "prod"
}

variable "api_min_instances" {
  type    = number
  default = 2
}

variable "api_max_instances" {
  type    = number
  default = 6
}

variable "web_min_instances" {
  type    = number
  default = 1
}

variable "web_max_instances" {
  type    = number
  default = 10
}

variable "worker_max_concurrent_executions" {
  type        = number
  default     = 10
  description = "Cloud Tasks dispatch rate and Cloud Run job concurrency must be reviewed against provider/database quotas."
}

variable "memorystore_memory_gb" {
  type        = number
  default     = 1
  description = "Memorystore Redis Standard HA capacity in GiB; review current regional pricing."
}

variable "waf_requests_per_ip_per_minute" {
  type    = number
  default = 300
}

variable "qdrant_url" {
  type        = string
  description = "HTTPS endpoint for the production hosted Qdrant cluster."
  validation {
    condition     = can(regex("^https://", var.qdrant_url))
    error_message = "qdrant_url must be HTTPS."
  }
}

variable "qdrant_collection" {
  type    = string
  default = "mindmesh_gemini_v1"
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
variable "enable_groq_secondary" {
  type        = bool
  default     = false
  description = "Create and inject GROQ_API_KEY_SECONDARY from Secret Manager when true. Used only after a 401 credential failure."
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

variable "supabase_storage_bucket" {
  type    = string
  default = "mindmesh-private"
}
