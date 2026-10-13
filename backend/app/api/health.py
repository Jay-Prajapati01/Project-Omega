"""Health check endpoint."""
import asyncio

import httpx
from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import HealthResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        version=__version__,
    )


@router.get("/health/detailed")
async def health_detailed():
    """Readiness probe: reports dependency booleans only.

    Public in every mode (no auth for orchestrators) and deliberately free of
    URLs, credentials, hostnames or stack traces — only ok/error flags
    (test API-001: liveness vs dependency health, no sensitive detail).
    """
    settings = get_settings()
    checks: dict[str, str] = {"app": "ok"}

    if settings.mindmesh_execution_mode in {"modal", "cloud"}:
        # Redis backs shared rate limits even when another store owns jobs.
        if settings.rate_limit_enabled or settings.job_backend == "redis":
            try:
                from app.services.jobs import client as redis_client

                await asyncio.to_thread(redis_client().ping)
                checks["redis"] = "ok"
            except Exception:  # noqa: BLE001
                checks["redis"] = "error"
        # Postgres: tenant/state store.
        try:
            from app.services.cloud_db import connect

            def _ping() -> None:
                with connect() as conn:
                    conn.execute("SELECT 1")

            await asyncio.to_thread(_ping)
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "error"
        # Qdrant: vector search.
        try:
            from app.services.vectorstore import get_client

            def _qping() -> None:
                get_client().get_collections()

            await asyncio.to_thread(_qping)
            checks["qdrant"] = "ok"
        except Exception:  # noqa: BLE001
            checks["qdrant"] = "error"
        overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
        return {"status": overall, "execution_mode": settings.mindmesh_execution_mode, "checks": checks}

    # Exception text can include internal base URLs (qdrant/ollama) — only
    # surface those details outside production (I-2).
    show_details = settings.environment != "production"
    checks.update({"ollama": "unknown", "qdrant": "unknown"})

    # Check Ollama
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=5) as client:
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                checks["ollama"] = "ok"
            else:
                checks["ollama"] = "error" if not show_details else f"error: status {resp.status_code}"
    except Exception as e:
        checks["ollama"] = "error" if not show_details else f"error: {str(e)[:100]}"

    # Check Qdrant
    try:
        from app.services.vectorstore import get_client
        client = get_client()
        client.get_collections()  # side-effect probe: raises when unreachable
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = "error" if not show_details else f"error: {str(e)[:100]}"

    overall_status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"

    payload = {
        "status": overall_status,
        "app": settings.app_name,
        "environment": settings.environment,
        "version": __version__,
        "checks": checks,
    }
    if show_details:
        payload.update(
            {
                "llm_model": settings.llm_model,
                "embedding_model": settings.embedding_model,
                "collection": settings.qdrant_collection,
            }
        )
    return payload
