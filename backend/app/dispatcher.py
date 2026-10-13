"""Private Cloud Tasks target: launch one Cloud Run Job execution per task.

Runs as its own Cloud Run service (same API image, different entrypoint:
``uvicorn app.dispatcher:app``) with ingress limited to internal traffic and
authentication required. Every task must additionally carry the shared
X-Dispatch-Secret header; Cloud Run IAM alone is not trusted for dispatch.

* Unknown or already-terminal jobs are acknowledged (200) so Cloud Tasks
  does not retry a pointless launch — duplicate deliveries are normal.
* A launch failure raises 502 so Cloud Tasks retries the dispatch with the
  queue's bounded backoff.
* A background sweeper reconciles the job table every minute and launches
  due queued jobs that have no recent launch — this is what recovers worker
  crashes, since a Cloud Run Job execution that dies mid-processing leaves
  its row for reconcile() to requeue.
"""
from __future__ import annotations

import asyncio
import hmac
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

from app import __version__
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_SWEEP_INTERVAL_SECONDS = 60
_LAUNCH_GUARD_SECONDS = 300


def _check_secret(provided: str) -> None:
    expected = get_settings().cloud_tasks_dispatch_secret
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(403, "Forbidden")


def create_dispatcher_app() -> FastAPI:
    launched: dict[str, float] = {}

    async def _sweep_forever() -> None:
        from app.services import jobs

        use_pg = jobs._pg()
        jobs_pg = None
        if use_pg:
            from app.services import jobs_pg as _jobs_pg

            jobs_pg = _jobs_pg
        while True:
            await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
            try:
                await asyncio.to_thread(jobs.reconcile)
                if jobs_pg is None:
                    continue  # legacy redis backend is polled by worker.py
                job_id = await asyncio.to_thread(jobs_pg.peek_due)
                last_launch = launched.get(job_id) if job_id is not None else None
                if job_id is None or (last_launch is not None and last_launch > time.monotonic() - _LAUNCH_GUARD_SECONDS):
                    continue
                from app.services import cloud_run_launcher

                await asyncio.to_thread(cloud_run_launcher.launch, job_id)
                launched[job_id] = time.monotonic()
            except Exception as exc:  # noqa: BLE001 — sweeper must never die
                logger.warning("dispatcher sweep deferred: %s", exc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting mindmesh-dispatcher v%s", __version__)
        task = asyncio.create_task(_sweep_forever())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            try:
                from app.services.cloud_db import close_pool

                close_pool()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Dispatcher Postgres pool shutdown failed: %s", type(exc).__name__)

    app = FastAPI(title="mindmesh-dispatcher", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "service": "mindmesh-dispatcher"}

    @app.post("/dispatch/{job_id}")
    async def dispatch(
        job_id: str,
        x_dispatch_secret: str = Header(default="", alias="X-Dispatch-Secret"),
    ) -> dict:
        _check_secret(x_dispatch_secret)
        from app.services import jobs

        try:
            job = await asyncio.to_thread(jobs.raw, job_id)
        except KeyError:
            return {"duplicate": True, "reason": "unknown-job"}
        if job["status"] != "queued":
            return {"duplicate": True, "status": job["status"]}
        last_launch = launched.get(job_id)
        if last_launch is not None and last_launch > time.monotonic() - _LAUNCH_GUARD_SECONDS:
            return {"duplicate": True, "reason": "recently-launched"}
        from app.services import cloud_run_launcher

        try:
            operation = await asyncio.to_thread(cloud_run_launcher.launch, job_id)
        except ConnectionError as exc:
            raise HTTPException(502, f"Launch failed: {exc}") from None
        launched[job_id] = time.monotonic()
        return {"launched": operation, "job_id": job_id}

    return app


app = create_dispatcher_app()
