"""Rate limiting and per-tenant quotas.

Two layers, both optional per config:

* ``IPRateLimitMiddleware`` — outermost, keyed by client IP, protects the
  auth path from unauthenticated floods. Runs before CORS issues are
  relevant only in that it must stay inside CORSMiddleware (see main.py).
* ``IdentityRateLimitMiddleware`` — runs after CloudAuthMiddleware so it can
  key limits by tenant/user identity with endpoint classes (read, chat,
  ingest, poll, write). Falls back to the client IP when no identity is set.

Redis is used when REDIS_URL is configured (shared across replicas — this is
the "distributed" requirement); otherwise an in-process store is used so a
single-node deployment still enforces limits.

Every 429 carries Retry-After, a stable error_code and the request id.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from urllib.parse import urlparse

from fastapi import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_memory_store: dict[str, list[float]] = defaultdict(list)
_last_sweep = 0.0

_REDIS = None
_REDIS_BROKEN = False


def _redis():
    """Return a shared Redis client for counters, or None when unavailable."""
    global _REDIS, _REDIS_BROKEN
    url = get_settings().redis_url
    if not url or _REDIS_BROKEN:
        return None
    if _REDIS is None:
        try:
            from redis import Redis

            settings = get_settings()
            options = {"decode_responses": True, "socket_timeout": 2, "socket_connect_timeout": 2}
            if settings.redis_password:
                options["password"] = settings.redis_password
            if settings.redis_ssl_ca_certs:
                options["ssl_ca_certs"] = settings.redis_ssl_ca_certs
            _REDIS = Redis.from_url(url, **options)
        except Exception as exc:  # noqa: BLE001
            if get_settings().environment == "production":
                logger.error("Could not initialize shared rate limiter (%s)", type(exc).__name__)
                raise RateLimitUnavailable from exc
            logger.warning("Rate limiter falling back to memory store: %s", type(exc).__name__)
            _REDIS_BROKEN = True
            return None
    return _REDIS


def hit(key: str, window: int, limit: int) -> tuple[bool, int]:
    """Record one hit. Returns (allowed, retry_after_seconds)."""
    now = time.time()
    r = _redis()
    if r is None and get_settings().environment == "production":
        raise RateLimitUnavailable("Shared rate-limit store is not configured")
    if r is not None:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, window)
            if int(count) > limit:
                ttl = r.ttl(key)
                return False, max(int(ttl) if ttl and ttl > 0 else window, 1)
            return True, 0
        except Exception as exc:  # noqa: BLE001
            if get_settings().environment == "production":
                logger.error("Distributed rate limit unavailable; rejecting request (%s)", type(exc).__name__)
                raise RateLimitUnavailable from exc
            logger.warning("Distributed rate limit unavailable (%s); using memory", type(exc).__name__)

    global _last_sweep
    if now - _last_sweep >= window:
        _last_sweep = now
        for k in [k for k, ts in _memory_store.items() if not ts or now - ts[-1] >= window]:
            _memory_store.pop(k, None)
    hits = [t for t in _memory_store[key] if now - t < window]
    if len(hits) >= limit:
        retry = int(window - (now - hits[0])) + 1
        _memory_store[key] = hits
        return False, max(retry, 1)
    hits.append(now)
    _memory_store[key] = hits
    return True, 0


class RateLimitUnavailable(RuntimeError):
    """Raised when production cannot reach the shared rate-limit store."""


# Endpoint classes from the beta rate-limit policy (audit file, section
# "Rate limiting and abuse control design").
_INGEST_PATHS = ("/videos/process", "/instagram/process", "/pdf/process",
                 "/documents/process", "/audio/process", "/web/process")
_CHAT_PATHS = ("/chat", "/search", "/compare")
_POLL_PATHS = ("/jobs/",)


def endpoint_class(method: str, path: str, api_prefix: str) -> tuple[str, int, int]:
    """Return (class_name, limit, window_seconds) for a request."""
    s = get_settings()
    rel = path[len(api_prefix):] if path.startswith(api_prefix) else path
    if method == "POST" and rel == "/contact":
        return "contact", s.rate_limit_contact_per_min, 60
    if any(rel.startswith(p) for p in _POLL_PATHS):
        return "poll", s.rate_limit_poll_per_min, 60
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        if any(rel.startswith(p) for p in _INGEST_PATHS):
            return "ingest", s.rate_limit_ingest_per_hour, 3600
        if any(rel == p or rel.startswith(p + "/") for p in _CHAT_PATHS):
            return "chat", s.rate_limit_chat_per_min, 60
        return "write", s.rate_limit_write_per_min, 60
    return "read", s.rate_limit_read_per_min, 60


def _identity(request: Request) -> str:
    from app.core.tenant import current_scope

    value = current_scope.get()
    if value is not None and value.tenant_id and value.user_id:
        return f"t:{value.tenant_id}:u:{value.user_id}"
    return "ip:" + _client_ip(request)


def _client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Only trust a proxy-added element; never use the caller-controlled
            # leftmost value. AWS ALB uses the last item, while GCP's global
            # external Application Load Balancer adds client IP then LB IP.
            values = [value.strip() for value in forwarded.split(",") if value.strip()]
            index = -2 if get_settings().trust_proxy_xff_index == "second-last" else -1
            return (values[index] if len(values) >= abs(index) else values[-1]) if values else "unknown"
    return request.client.host if request.client else "unknown"


def _reject(request: Request, retry_after: int, cls: str) -> JSONResponse:
    request_id = request.headers.get("x-request-id", "") or uuid.uuid4().hex
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded for {cls} requests. Try again in {retry_after}s.",
            "error_code": "RATE_LIMITED",
            "request_id": request_id,
        },
        headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
    )


class IPRateLimitMiddleware:
    """Outer per-IP limiter. Liveness probes and preflights are exempt."""

    def __init__(self, app, max_requests: int = 120, window: int = 60, skip_prefixes: tuple[str, ...] = ()):
        self.app = app
        self.max_requests = max_requests
        self.window = window
        self.skip_prefixes = skip_prefixes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope.get("method") == "OPTIONS" or not get_settings().rate_limit_enabled:
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if any(path == p or path.startswith(p) for p in self.skip_prefixes):
            return await self.app(scope, receive, send)

        from fastapi import Request as FastAPIRequest

        request = FastAPIRequest(scope, receive)
        key = "mm:rl:ip:" + _client_ip(request)
        try:
            allowed, retry = hit(key, self.window, self.max_requests)
        except RateLimitUnavailable:
            return await _unavailable(request)(scope, receive, send)
        if not allowed:
            metrics_key = "rate_limited_total"
            from app.core import metrics

            metrics.inc(metrics_key, layer="ip")
            return await _reject(request, retry, "ip")(scope, receive, send)
        return await self.app(scope, receive, send)


class IdentityRateLimitMiddleware:
    """Inner per-identity limiter with endpoint classes.

    Must be added AFTER IPRateLimitMiddleware and BEFORE CloudAuthMiddleware
    is *not* required — it only needs the scope ContextVar set by
    CloudAuthMiddleware, which wraps everything added before it.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await self.app(scope, receive, send)

        from fastapi import Request as FastAPIRequest

        request = FastAPIRequest(scope, receive)
        path = scope.get("path", "")
        if any(path == p or path.startswith(p) for p in (f"{settings.api_prefix}/health", "/health")):
            return await self.app(scope, receive, send)

        cls, limit, window = endpoint_class(scope.get("method", "GET"), path, settings.api_prefix)
        key = f"mm:rl:{cls}:" + _identity(request)
        try:
            allowed, retry = hit(key, window, limit)
        except RateLimitUnavailable:
            return await _unavailable(request)(scope, receive, send)
        if not allowed:
            from app.core import metrics

            metrics.inc("rate_limited_total", layer="identity", cls=cls)
            logger.info("rate_limited class=%s path=%s retry_after=%s", cls, path, retry)
            return await _reject(request, retry, cls)(scope, receive, send)
        return await self.app(scope, receive, send)


def _unavailable(request: Request) -> JSONResponse:
    request_id = request.headers.get("x-request-id", "") or uuid.uuid4().hex
    return JSONResponse(
        status_code=503,
        content={"detail": "Request protection is temporarily unavailable", "error_code": "RATE_LIMIT_UNAVAILABLE", "request_id": request_id},
        headers={"Retry-After": "5", "X-Request-ID": request_id},
    )


def quota_hit(tenant_id: str, kind: str, amount: int, daily_limit: int) -> tuple[bool, int]:
    """Accumulate a daily per-tenant quota. Returns (allowed, used).

    Counter layers, in order: Redis INCRBY when configured, a single atomic
    Postgres upsert when running in a cloud mode with a database, otherwise
    the in-process store. The Postgres path is what makes large upload-byte
    quotas safe without Redis: one numeric row per tenant/kind/day instead of
    one timestamp per byte.
    """
    settings = get_settings()
    if daily_limit <= 0:
        return True, 0
    day = time.strftime("%Y%m%d")
    key = f"mm:quota:{kind}:{tenant_id}:{day}"
    r = _redis()
    if r is not None:
        try:
            used = r.incrby(key, amount)
            if used == amount:
                r.expire(key, 172800)  # keep two days for timezone slack
            return (int(used) <= daily_limit, int(used))
        except Exception as exc:  # noqa: BLE001
            if settings.environment == "production":
                logger.error("Quota accounting unavailable; rejecting request (%s)", type(exc).__name__)
                from fastapi import HTTPException

                raise HTTPException(status_code=503, detail="Usage quota service is temporarily unavailable") from exc
            logger.warning("Quota accounting unavailable (%s); skipping", type(exc).__name__)
            return True, 0
    if settings.mindmesh_execution_mode in {"modal", "cloud"} and settings.supabase_db_url:
        try:
            from app.services import cloud_db

            used = cloud_db.quota_add(tenant_id, kind, day, amount)
            return (used <= daily_limit, used)
        except Exception as exc:  # noqa: BLE001
            if settings.environment == "production":
                logger.error("Postgres quota accounting unavailable; rejecting request (%s)", type(exc).__name__)
                from fastapi import HTTPException

                raise HTTPException(status_code=503, detail="Usage quota service is temporarily unavailable") from exc
            logger.warning("Postgres quota accounting unavailable (%s); skipping", type(exc).__name__)
            return True, 0
    hits = _memory_store[key]
    now = time.time()
    hits = [t for t in hits if now - t < 86400]
    total = len(hits) + amount
    if amount > 0:
        hits.extend([now] * amount)
    _memory_store[key] = hits
    return (total <= daily_limit, total)


def reset_for_tests() -> None:
    global _REDIS, _REDIS_BROKEN, _last_sweep
    _memory_store.clear()
    _last_sweep = 0.0
    _REDIS = None
    _REDIS_BROKEN = False


_ = urlparse  # kept for potential URL-based class hooks
