"""Validate Supabase tokens remotely and resolve active membership server-side.

Identity comes exclusively from the bearer token validated against Supabase;
tenant membership comes from the mm_memberships table. No header, query
parameter or body field can influence either (audit P0-3/P0-4).
"""
import asyncio
from uuid import UUID

import httpx
from fastapi import Request
from starlette.responses import JSONResponse

from app.core import metrics
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.tenant import Scope, current_scope
from app.services.cloud_db import connect

logger = get_logger(__name__)


def resolve_user(user_id: str) -> Scope:
    # No caching: membership revocation must take effect on the very next
    # request (production-ready definition — "lose it immediately").
    with connect() as conn:
        rows = conn.execute("SELECT tenant_id FROM public.mm_memberships WHERE user_id=%s AND active",
                            (user_id,)).fetchall()
        if len(rows) != 1:
            raise PermissionError("Exactly one active personal workspace is required")
        members = conn.execute(
            "SELECT count(*) FROM public.mm_memberships WHERE tenant_id=%s AND active",
            (rows[0][0],),
        ).fetchone()[0]
    if members != 1:
        raise PermissionError("A personal workspace must have exactly one active member")
    return Scope(str(rows[0][0]), user_id)


class CloudAuthMiddleware:
    def __init__(self, app, local_identity: bool = False):
        self.app = app
        self.local_identity = local_identity

    async def __call__(self, scope, receive, send):
        cfg = get_settings()
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        # Liveness/readiness probes stay unauthenticated but must not leak
        # dependency detail: health handlers are sanitized separately.
        # The contact form is intentionally public (anonymous visitors only).
        if scope.get("path") in {
            "/health",
            cfg.api_prefix + "/health",
            cfg.api_prefix + "/health/detailed",
            cfg.api_prefix + "/contact",
            cfg.api_prefix + "/v1/public/plans",
            cfg.api_prefix + "/v1/analytics/events",
        }:
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or len(auth) > 8192:
            metrics.inc("auth_failures_total", reason="missing_token")
            return await JSONResponse({"detail": "Sign in required", "error_code": "AUTH_REQUIRED"},
                                      status_code=401)(scope, receive, send)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(cfg.supabase_url + "/auth/v1/user",
                    headers={"Authorization": auth, "apikey": cfg.supabase_anon_key})
            if response.status_code != 200:
                metrics.inc("auth_failures_total", reason="invalid_token")
                return await JSONResponse({"detail": "Invalid session", "error_code": "AUTH_INVALID"},
                                          status_code=401)(scope, receive, send)
            user_id = str(UUID(response.json()["id"]))
            # Local compute uses the verified Auth UUID as its personal namespace.
            # Cloud workers resolve durable membership in Postgres instead.
            owner = Scope(user_id, user_id) if self.local_identity else await asyncio.to_thread(resolve_user, user_id)
        except PermissionError:
            metrics.inc("auth_failures_total", reason="no_membership")
            return await JSONResponse({"detail": "No active workspace membership", "error_code": "NO_MEMBERSHIP"},
                                      status_code=403)(scope, receive, send)
        except Exception as exc:  # noqa: BLE001 — network/DB failures become 503
            if not isinstance(exc, (httpx.HTTPError, OSError, ValueError)):
                logger.warning("auth backend unavailable: %s", type(exc).__name__)
            metrics.inc("auth_failures_total", reason="backend_unavailable")
            return await JSONResponse({"detail": "Authentication unavailable", "error_code": "AUTH_UNAVAILABLE"},
                                      status_code=503)(scope, receive, send)
        metrics.inc("auth_success_total")
        token = current_scope.set(owner)
        try:
            await self.app(scope, receive, send)
        finally:
            current_scope.reset(token)
