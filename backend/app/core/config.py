"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # App
    app_name: str = "MindMesh"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    data_dir: str = "/app/data"
    mindmesh_execution_mode: str = "local"
    auth_enabled: bool = False
    modal_app_name: str = "mindmesh-workers"
    modal_environment: str = "main"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""
    # Per-process ceiling. Multiply by maximum API + worker instances when
    # sizing the Supabase pooler / database connection budget.
    supabase_db_pool_max_size: int = 5
    supabase_db_pool_timeout_seconds: float = 10
    supabase_storage_bucket: str = "mindmesh-private"
    redis_url: str = ""
    qdrant_api_key: str = ""
    job_ttl_seconds: int = 604800
    worker_process: bool = False
    worker_poll_seconds: int = 10
    # Job lifecycle store: redis (legacy/Modal), postgres (durable rows in
    # Supabase), gcp (Postgres rows + Cloud Tasks dispatch + Cloud Run Jobs).
    job_backend: str = "redis"
    # Google Cloud dispatch (only required when JOB_BACKEND=gcp).
    gcp_project_id: str = ""
    gcp_region: str = ""
    cloud_tasks_queue: str = "mindmesh-jobs"
    cloud_tasks_dispatcher_url: str = ""
    cloud_tasks_service_account: str = ""
    # Shared secret the dispatcher checks on every task (Cloud Tasks sends it
    # as X-Dispatch-Secret alongside the OIDC token; both live in Secret Manager).
    cloud_tasks_dispatch_secret: str = ""
    cloud_run_job_name: str = "mindmesh-worker"
    llm_provider: str = ""
    xai_api_key: str = ""
    xai_model: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    # Commerce and BYOK secrets stay server-only. BYOK_ENCRYPTION_KEY is a
    # base64url-encoded 32-byte AES-256 key from Secret Manager; never a
    # NEXT_PUBLIC value or a checked-in development default.
    byok_encryption_key: str = ""
    promo_hmac_pepper: str = ""
    owner_bootstrap_user_id: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payments_enabled: bool = False
    groq_whisper_model: str = "whisper-large-v3-turbo"

    # Security — when set (any environment), mutating endpoints require a
    # matching X-API-Key header. Empty keeps local development open.
    # Cloud mode ignores this entirely: membership + bearer always win.
    api_key: str = ""

    # Request body caps enforced in middleware BEFORE parsing (a huge body
    # otherwise buffers/spools to disk before any in-handler size check).
    max_json_body_size: int = 10 * 1024 * 1024  # 10 MB for JSON endpoints
    # multipart: max_upload_size + slack for form fields/boundaries
    max_multipart_body_size: int = 210 * 1024 * 1024

    # SSRF guard for outbound fetches (web ingestion, PDF URLs, crawler).
    # Blocks loopback/private/link-local/metadata addresses. Set to false
    # only if you intentionally ingest pages from internal addresses.
    ssrf_block_private: bool = True

    # Rate limiting — on by default in every environment.
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 120
    rate_limit_window: int = 60
    # Identity classes (per user, per tenant fallback to IP when anonymous).
    rate_limit_read_per_min: int = 120
    rate_limit_write_per_min: int = 60
    rate_limit_chat_per_min: int = 30
    rate_limit_poll_per_min: int = 60
    rate_limit_ingest_per_hour: int = 20
    rate_limit_contact_per_min: int = 5
    # Per-tenant daily quotas (0 disables the quota).
    max_jobs_per_tenant_per_day: int = 200
    max_ai_requests_per_tenant_per_day: int = 500
    max_upload_bytes_per_tenant_per_day: int = 5 * 1024 * 1024 * 1024  # 5 GB
    # Hard cap on how long the SSE status stream waits for a terminal job.
    sse_max_wait_seconds: int = 7200
    # Retention for mirrored terminal job results in Postgres.
    job_result_retention_days: int = 30
    # Trust X-Forwarded-For only when behind a reverse proxy you control.
    trust_proxy: bool = False

    # Concurrency cap for heavy pipelines (transcription, OCR, downloads).
    max_concurrent_heavy_tasks: int = 2

    # Parser limits (zip bombs, huge PDFs).
    max_pdf_pages: int = 500
    zip_max_uncompressed_bytes: int = 500 * 1024 * 1024  # 500 MB
    zip_max_ratio: int = 200

    # Outbound fetch limits.
    fetch_max_bytes: int = 20 * 1024 * 1024  # 20 MB
    fetch_timeout_seconds: int = 30

    # Uploads
    max_upload_size: int = 200 * 1024 * 1024  # 200 MB

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "mindmesh"

    # Ollama
    # Defaults tuned for CPU-only / 16 GB laptops. For a powerful machine or
    # GPU, switch to llm_model=qwen3:8b and embedding_model=bge-m3 (dim 1024).
    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:3b"
    # Embedding provider: ollama (local dev / Modal CPU fallback) or gemini
    # (Google Cloud production). embedding_model names the model for the
    # active provider, e.g. nomic-embed-text or gemini-embedding-2.
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    gemini_api_key: str = ""
    gemini_api_base: str = "https://generativelanguage.googleapis.com"

    # Instagram (optional - enables authenticated access to posts)
    # Set ig_username and ig_password to access private posts or posts
    # that require login. When empty, public posts are accessed without auth.
    # Required for: private accounts, age-restricted content, stories
    ig_username: str = ""
    ig_password: str = ""

    # Crawl4AI
    crawl4ai_headless: bool = True
    crawl4ai_cache_mode: str = "bypass"

    # Ingestion / retrieval
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 5
    # Baseline floor for hybrid relevance (semantic + lexical rerank) in chat.
    chat_min_score: float = 0.34

    # PDF Pipeline
    pdf_max_file_size: int = 100 * 1024 * 1024  # 100 MB
    pdf_ocr_dpi: int = 300
    pdf_min_text_per_page: int = 40

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def embedding_dim_for_model(self) -> int:
        """Return the correct embedding dimension for the configured model."""
        if self.embedding_model.startswith("gemini-embedding"):
            # Gemini truncates to outputDimensionality via Matryoshka; the
            # operator chooses the size through EMBEDDING_DIM (768 default).
            return self.embedding_dim
        model_dims = {
            "nomic-embed-text": 768,
            "bge-m3": 1024,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
        }
        return model_dims.get(self.embedding_model, self.embedding_dim)

    @property
    def embedding_label(self) -> str:
        """Stable payload label identifying the embedding vector space.

        Collections must never mix vector spaces, so the label always encodes
        the provider and model. Legacy Modal collections keep "BAAI/bge-m3".
        """
        if self.embedding_provider == "gemini":
            return f"gemini:{self.embedding_model}"
        if self.mindmesh_execution_mode == "modal" and self.embedding_model == "bge-m3":
            return "BAAI/bge-m3"
        return f"{self.embedding_provider}:{self.embedding_model}"

    @model_validator(mode="after")
    def validate_critical_settings(self) -> "Settings":
        """Validate critical settings at startup."""
        import logging
        logger = logging.getLogger(__name__)

        # Normalize so "Production"/" PROD" cannot silently disable the
        # API-key guard or the rate limiter (exact-case comparisons before).
        self.environment = self.environment.strip().lower()
        self.mindmesh_execution_mode = self.mindmesh_execution_mode.strip().lower()
        if self.mindmesh_execution_mode not in {"local", "modal", "cloud"}:
            raise ValueError("MINDMESH_EXECUTION_MODE must be local, modal or cloud")
        if self.environment == "production" and self.mindmesh_execution_mode == "local":
            raise ValueError("Production requires a cloud execution mode")
        if self.environment == "production" and not self.rate_limit_enabled:
            raise ValueError("Production requires RATE_LIMIT_ENABLED=true")
        if self.environment == "production" and not self.redis_url:
            raise ValueError("Production rate limiting requires REDIS_URL so limits are shared across replicas")
        if self.environment == "production" and min(
            self.rate_limit_max_requests, self.rate_limit_window,
            self.rate_limit_read_per_min, self.rate_limit_write_per_min,
            self.rate_limit_chat_per_min, self.rate_limit_poll_per_min,
            self.rate_limit_ingest_per_hour, self.rate_limit_contact_per_min,
            self.max_jobs_per_tenant_per_day, self.max_ai_requests_per_tenant_per_day,
            self.max_upload_bytes_per_tenant_per_day,
        ) <= 0:
            raise ValueError("Production rate limits and daily quotas must all be greater than zero")
        if self.auth_enabled and not (self.supabase_url and self.supabase_anon_key):
            raise ValueError("Authentication requires SUPABASE_URL and SUPABASE_ANON_KEY")
        if self.embedding_provider not in {"ollama", "gemini"}:
            raise ValueError("EMBEDDING_PROVIDER must be ollama or gemini")
        if self.job_backend not in {"redis", "postgres", "gcp"}:
            raise ValueError("JOB_BACKEND must be redis, postgres or gcp")
        if not 1 <= self.supabase_db_pool_max_size <= 32:
            raise ValueError("SUPABASE_DB_POOL_MAX_SIZE must be between 1 and 32")
        if not 1 <= self.supabase_db_pool_timeout_seconds <= 60:
            raise ValueError("SUPABASE_DB_POOL_TIMEOUT_SECONDS must be between 1 and 60")
        if not 1 <= self.worker_poll_seconds <= 300:
            raise ValueError("WORKER_POLL_SECONDS must be between 1 and 300")
        if self.mindmesh_execution_mode in {"modal", "cloud"}:
            from urllib.parse import urlparse
            if not all((self.supabase_url, self.supabase_anon_key, self.supabase_service_role_key,
                        self.supabase_db_url, self.qdrant_api_key)):
                raise ValueError("Cloud mode requires Supabase, database and Qdrant credentials")
            for endpoint in (self.supabase_url, self.qdrant_url):
                parsed = urlparse(endpoint)
                if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "qdrant"}:
                    raise ValueError("Cloud service endpoints must use public HTTPS")
            if "sslmode=require" not in self.supabase_db_url and "sslmode=verify-full" not in self.supabase_db_url:
                raise ValueError("SUPABASE_DB_URL must require TLS")
            if not self.ssrf_block_private or not self.crawl4ai_headless or self.crawl4ai_cache_mode != "bypass":
                raise ValueError("Cloud browsers require SSRF protection, headless mode and disabled page caching")
            if self.mindmesh_execution_mode == "modal":
                if not self.redis_url:
                    raise ValueError("Modal mode requires a Redis URL")
                if not self.redis_url.startswith("rediss://"):
                    raise ValueError("Cloud Redis must use TLS (rediss://)")
                if self.embedding_model != "bge-m3" or self.embedding_dim != 1024:
                    raise ValueError("Modal mode requires EMBEDDING_MODEL=bge-m3 and EMBEDDING_DIM=1024")
                if self.qdrant_collection == "mindmesh":
                    raise ValueError("Use a new collection for BGE-M3, e.g. mindmesh_bge_m3_v1")
            else:
                # Google Cloud execution. Redis is only authoritative for the
                # legacy redis job backend; postgres/gcp persist jobs in
                # Supabase and must not require any Redis server.
                if self.redis_url and not self.redis_url.startswith("rediss://"):
                    raise ValueError("Cloud Redis must use TLS (rediss://)")
                if self.job_backend == "redis" and not self.redis_url:
                    raise ValueError("JOB_BACKEND=redis requires REDIS_URL")
                if self.embedding_provider == "gemini":
                    if not self.gemini_api_key:
                        raise ValueError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
                    if not 128 <= self.embedding_dim <= 3072:
                        raise ValueError("Gemini EMBEDDING_DIM must be between 128 and 3072")
                    if self.qdrant_collection == "mindmesh":
                        raise ValueError("Use a new collection for Gemini, e.g. mindmesh_gemini_v1")
                if self.job_backend == "gcp":
                    missing = [name for name, value in (
                        ("GCP_PROJECT_ID", self.gcp_project_id),
                        ("GCP_REGION", self.gcp_region),
                        ("CLOUD_TASKS_QUEUE", self.cloud_tasks_queue),
                        ("CLOUD_TASKS_DISPATCHER_URL", self.cloud_tasks_dispatcher_url),
                        ("CLOUD_TASKS_SERVICE_ACCOUNT", self.cloud_tasks_service_account),
                        ("CLOUD_TASKS_DISPATCH_SECRET", self.cloud_tasks_dispatch_secret),
                        ("CLOUD_RUN_JOB_NAME", self.cloud_run_job_name),
                    ) if not value]
                    if missing:
                        raise ValueError(f"JOB_BACKEND=gcp requires {', '.join(missing)}")
                    dispatcher = urlparse(self.cloud_tasks_dispatcher_url)
                    if dispatcher.scheme != "https":
                        raise ValueError("CLOUD_TASKS_DISPATCHER_URL must use public HTTPS")
        if self.mindmesh_execution_mode == "cloud":
            if self.llm_provider not in {"xai", "groq"}:
                raise ValueError("Cloud mode requires an explicit LLM_PROVIDER: xai or groq")
            if self.llm_provider == "xai" and not (self.xai_api_key and self.xai_model):
                raise ValueError("xAI requires XAI_API_KEY and XAI_MODEL")
            if self.llm_provider == "groq" and not self.groq_api_key:
                raise ValueError("Groq requires GROQ_API_KEY")
            from urllib.parse import urlparse
            if any(urlparse(o).scheme != "https" or urlparse(o).hostname in {"localhost", "127.0.0.1"}
                   for o in self.cors_origin_list):
                raise ValueError("Cloud CORS origins must use public HTTPS")

        # allow_credentials=True is hardcoded in main.py; Starlette would
        # reflect any request Origin if "*" were allowed — reject it outright.
        if "*" in self.cors_origin_list:
            raise ValueError(
                "CORS_ORIGINS must not contain '*' when credentials are "
                "allowed. List explicit origins instead."
            )

        if self.environment == "production":
            if self.cors_origins == "http://localhost:3000,http://127.0.0.1:3000":
                logger.warning("CORS origins are set to localhost in production! Set CORS_ORIGINS env var.")
            if self.data_dir == "/app/data":
                logger.warning("Using default data_dir in production. Set DATA_DIR env var.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
