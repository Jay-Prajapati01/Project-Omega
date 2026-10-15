"""MindMesh FastAPI application entrypoint.

`create_app()` builds a fully wired application instance; the module-level
`app` is the production instance (imported by uvicorn and the test suite).
Tests build a second instance in modal mode to verify the cloud auth path.
"""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute

from app import __version__
from app.api import (
    analytics,
    chat,
    commerce,
    contact,
    health,
    instagram,
    graph,
    mobile,
    notes,
    search,
    sources,
    stats,
    videos,
)
from app.core import metrics
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import IdentityRateLimitMiddleware, IPRateLimitMiddleware
from app.core.security import require_key

configure_logging()
logger = get_logger(__name__)


# --- Request body size limits (checked BEFORE FastAPI/Starlette parse) ---
class _BodyTooLarge(Exception):
    """Raised from the guarded receive() when a streamed body exceeds the cap."""


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before they are buffered/spooled.

    Content-Length is checked up-front; chunked bodies are counted as they
    stream and aborted at the cap.
    """

    def __init__(self, app, json_limit: int, multipart_limit: int):
        self.app = app
        self.json_limit = json_limit
        self.multipart_limit = multipart_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        content_type = headers.get("content-type", "")
        limit = self.multipart_limit if content_type.startswith("multipart/form-data") else self.json_limit

        content_length = headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > limit:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large (max {limit} bytes)",
                                 "error_code": "PAYLOAD_TOO_LARGE"},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0

        async def guarded_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, guarded_receive, send)
        except _BodyTooLarge:
            response = JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large (max {limit} bytes)",
                         "error_code": "PAYLOAD_TOO_LARGE"},
            )
            try:
                await response(scope, receive, send)
            except Exception:  # noqa: BLE001 — response may already be streaming
                logger.warning("Could not deliver 413 for oversized body")


# --- Concurrency limiter for heavy ingestion pipelines (M-9) ---
_heavy_semaphore: asyncio.Semaphore | None = None


class HeavyTaskMiddleware:
    """Limit concurrent heavy ingestion tasks (audio, PDF, video, web, Instagram)."""

    HEAVY_PREFIXES = ("/api/audio", "/api/pdf", "/api/videos", "/api/instagram", "/api/documents", "/api/web")

    def __init__(self, app, max_tasks: int = 2):
        global _heavy_semaphore
        self.app = app
        _heavy_semaphore = asyncio.Semaphore(max_tasks)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if get_settings().mindmesh_execution_mode in {"modal", "cloud"} or not path.startswith(self.HEAVY_PREFIXES):
            return await self.app(scope, receive, send)

        async with _heavy_semaphore:
            return await self.app(scope, receive, send)


def _route_class(path: str, api_prefix: str) -> str:
    """Low-cardinality route label for metrics (never includes resource IDs)."""
    parts = [p for p in path.split("/") if p][:3]
    if len(parts) >= 2 and parts[0] == api_prefix.strip("/"):
        return "/".join(parts[:2])
    return "/" + (parts[0] if parts else "")


class ResponseGuardMiddleware:
    """Outermost middleware: security headers, request IDs and HTTP metrics.

    * X-Request-ID (propagated from the client when supplied) on every response
    * X-Content-Type-Options / X-Frame-Options / Referrer-Policy / Permissions-Policy
    * HSTS when ENVIRONMENT=production
    * Cache-Control: no-store on authenticated API responses (never cached)
    * per-status/route metrics counters
    """

    def __init__(self, app, production: bool, api_prefix: str):
        self.app = app
        self.production = production
        self.api_prefix = api_prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = headers.get("x-request-id", "")[:128] or uuid.uuid4().hex
        path = scope.get("path", "")
        route = _route_class(path, self.api_prefix)
        started = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                raw = list(message.get("headers", []))

                def add(name: str, value: str) -> None:
                    raw.append((name.encode("latin-1"), value.encode("latin-1")))

                existing = {k.decode("latin-1").lower() for k, _ in raw}
                if "x-request-id" not in existing:
                    add("X-Request-ID", request_id)
                add("X-Content-Type-Options", "nosniff")
                add("X-Frame-Options", "DENY")
                add("Referrer-Policy", "no-referrer")
                add("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                if self.production:
                    add("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
                if path.startswith(self.api_prefix) and "cache-control" not in existing:
                    add("Cache-Control", "no-store")
                message["headers"] = raw
                metrics.inc("http_requests_total", status=str(message["status"]), route=route)
                metrics.inc("http_duration_seconds_sum", time.perf_counter() - started, route=route)
            await send(message)

        # Account-based clients must never silently use the anonymous local
        # development workspace. This header requests a stricter policy; it
        # supplies no identity and never bypasses bearer verification.
        if headers.get("x-mindmesh-require-auth") == "true":
            cfg = get_settings()
            if not cfg.auth_enabled and cfg.mindmesh_execution_mode not in {"modal", "cloud"}:
                return await JSONResponse(
                    {"detail": "Enable AUTH_ENABLED=true on the local backend before using the companion app.",
                     "error_code": "AUTH_CONFIGURATION_REQUIRED"}, status_code=503,
                )(scope, receive, send_wrapper)
        return await self.app(scope, receive, send_wrapper)


def _only_methods(router, methods: set[str]):
    """Return a copy of *router* exposing only routes whose methods intersect."""
    filtered = router.__class__()
    for route in router.routes:
        if isinstance(route, APIRoute) and set(route.methods) & methods:
            filtered.routes.append(route)
    return filtered


def create_app() -> FastAPI:
    """Build a fully wired FastAPI instance from the current settings."""
    settings = get_settings()
    is_production = settings.environment == "production"
    
    # Initialize adaptive backend selection (Groq -> HF Spaces -> local).
    from app.core.backend_config import backend, backend_name

    backend_config = backend()  # pulls from env (GROQ_API_KEY / HF_SPACE_URL)
    logger.info(
        "Active AI backend: %s (%s)",
        backend_name(),
        {k: v for k, v in backend_config.items() if k != "key"},  # never log secrets
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting %s v%s", settings.app_name, __version__)
        if settings.mindmesh_execution_mode == "local" and is_production:
            logger.error("Local execution mode is not allowed in production; refusing unsafe configuration.")
        if settings.rate_limit_enabled and not settings.redis_url:
            logger.error("Production rate limiting requires a shared REDIS_URL.")
        try:
            from app.services import vectorstore

            vectorstore.ensure_collection()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant not ready at startup: %s", exc)
        try:
            yield
        finally:
            try:
                from app.services.cloud_db import close_pool

                close_pool()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Postgres pool shutdown failed: %s", type(exc).__name__)
            logger.info("Shutting down %s", settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="AI Personal Knowledge Operating System",
        lifespan=lifespan,
        # /docs + /openapi.json expose the full API surface: keep them out of
        # production deployments (I-1).
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # --- Middleware stack ---------------------------------------------------
    # Starlette wraps in reverse addition order: FIRST added = INNERMOST.
    # Request flow (outer -> inner):
    #   ResponseGuard -> CORS -> IP rate limit -> body size -> cloud auth
    #     -> identity rate limit -> heavy-task -> route
    # CORS is outside both limiters so every 429/413 carries CORS headers;
    # cloud auth is outside the identity limiter so limits key on real identity.

    # 1 (innermost) — concurrency cap for heavy local pipelines.
    app.add_middleware(
        HeavyTaskMiddleware,
        max_tasks=settings.max_concurrent_heavy_tasks,
    )

    # 2 — per-identity/endpoint-class limits; reads the scope ContextVar that
    # CloudAuthMiddleware (added next, therefore outer) has already set.
    if settings.rate_limit_enabled:
        app.add_middleware(IdentityRateLimitMiddleware)

    # Identity is independent of where ingestion runs.
    if settings.auth_enabled or settings.mindmesh_execution_mode in {"modal", "cloud"}:
        from app.core.cloud_auth import CloudAuthMiddleware

        app.add_middleware(CloudAuthMiddleware, local_identity=settings.mindmesh_execution_mode == "local")

    # 4 — oversized-body rejection before routing/parsing.
    app.add_middleware(
        BodySizeLimitMiddleware,
        json_limit=settings.max_json_body_size,
        multipart_limit=settings.max_multipart_body_size,
    )

    # 5 — outer per-IP limiter protecting the auth path from unauthenticated floods.
    if settings.rate_limit_enabled:
        _skip = [f"{settings.api_prefix}/health", "/health"]
        if not is_production:
            _skip += ["/docs", "/redoc", "/openapi.json"]
        app.add_middleware(
            IPRateLimitMiddleware,
            max_requests=settings.rate_limit_max_requests,
            window=settings.rate_limit_window,
            skip_prefixes=tuple(_skip),
        )

    # 6 — CORS wraps both limiters so browser clients see proper error headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Job-ID", "X-Request-ID", "Retry-After"],
    )

    # 7 (outermost) — security headers, request IDs, metrics.
    app.add_middleware(
        ResponseGuardMiddleware,
        production=is_production,
        api_prefix=settings.api_prefix,
    )

    # --- Exception handlers ------------------------------------------------
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Map domain ValueErrors (e.g. empty content, SSRF blocks) to a 400."""
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid request" if is_production else str(exc)},
        )

    from app.services.commerce import CommerceError

    @app.exception_handler(CommerceError)
    async def commerce_error_handler(request: Request, exc: CommerceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, "message": str(exc)}})

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
        """Ownership/scope failures are 403 — never a leaked 500 stack."""
        metrics.inc("authz_denied_total")
        return JSONResponse(
            status_code=403,
            content={"detail": "Not authorized", "error_code": "FORBIDDEN"},
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        """Missing resources are 404 without revealing whether they exist."""
        return JSONResponse(status_code=404, content={"detail": "Not found", "error_code": "NOT_FOUND"})

    # --- Routes ------------------------------------------------------------
    mutating = [Depends(require_key)]

    if settings.mindmesh_execution_mode in {"modal", "cloud"}:
        from app.api.cloud_jobs import router as jobs_router

        # Facade routes carry require_key (scope()) as defense-in-depth behind
        # CloudAuthMiddleware — identity must be present even if ordering changes.
        app.include_router(jobs_router, prefix=settings.api_prefix, dependencies=mutating)
        # Legacy synchronous ingestion/search/chat/compare POST handlers are NOT
        # mounted in cloud mode: every heavy path goes through the job facade so
        # tenant scope, idempotency and leases always apply (audit P0-15).
        # Chat keeps its GET conversation-history route (facade has no equivalent).
        post_only: list = []
        app.include_router(
            _only_methods(chat.router, {"GET"}), prefix=settings.api_prefix, dependencies=mutating
        )
        # Reads get the same dependency as defense-in-depth: even if middleware
        # ordering is ever broken, routes still demand a real scope.
        read_deps = mutating
    else:
        post_only = [videos, instagram, search, chat]
        read_deps = mutating if settings.auth_enabled else []

    # Graph rebuilds are local-only; cloud deployments run costly extraction
    # through the job facade and expose only the scoped graph read endpoint.
    graph_router = _only_methods(graph.router, {"GET"}) if settings.mindmesh_execution_mode in {"modal", "cloud"} else graph.router
    read_routers = [notes.router, stats.router, sources.router, graph_router]

    app.include_router(health.router, prefix=settings.api_prefix)
    # Public contact intake: intentionally outside `mutating`/`read_deps` so
    # anonymous visitors can reach it (CloudAuthMiddleware exempts the path).
    app.include_router(contact.router, prefix=settings.api_prefix)
    app.include_router(commerce.public_router, prefix=settings.api_prefix)
    app.include_router(analytics.public_router, prefix=settings.api_prefix)
    app.include_router(commerce.router, prefix=settings.api_prefix, dependencies=mutating)
    app.include_router(analytics.router, prefix=settings.api_prefix, dependencies=mutating)
    # The companion receives an immediate, durable receipt here; it reuses the
    # same verified scope and ingestion handlers as the website.
    app.include_router(mobile.router, prefix=settings.api_prefix, dependencies=mutating)
    for router in post_only:
        app.include_router(router.router, prefix=settings.api_prefix, dependencies=mutating)
    for router in read_routers:
        app.include_router(router, prefix=settings.api_prefix, dependencies=read_deps)

    @app.get("/")
    async def root() -> dict:
        cfg = get_settings()
        return {
            "app": cfg.app_name,
            "docs": "/docs" if not is_production else None,
            "health": f"{cfg.api_prefix}/health",
        }

    @app.get("/health")
    async def health_alias():
        """Bare /health alias for probes that do not use the /api prefix."""
        return await health.health()

    @app.get(f"{settings.api_prefix}/metrics")
    async def prometheus_metrics() -> PlainTextResponse:
        """Process metrics (counters/gauges only — no request or tenant data)."""
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

    return app


app = create_app()
