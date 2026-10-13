"""Request authentication guard for mutating endpoints.

Modal (cloud) mode: the guard re-asserts an active tenant scope; identity
itself was already validated by CloudAuthMiddleware from the Supabase bearer
token and the membership table — never from client-supplied fields.

Local mode: when API_KEY is configured, requests must present a matching
X-API-Key header (constant-time comparison). With no key configured the API
stays open for development — that is the documented local default.
"""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_key(key: str | None = Security(_api_key_header)) -> None:
    from app.core.tenant import authenticated, scope

    if authenticated():
        # Never accept tenant identity from the request: scope() reads the
        # ContextVar set by CloudAuthMiddleware from the validated token.
        scope()
        return
    settings = get_settings()
    if not settings.api_key:
        # Local development without API_KEY: open by design.
        return
    if not key or not secrets.compare_digest(key.encode(), settings.api_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
