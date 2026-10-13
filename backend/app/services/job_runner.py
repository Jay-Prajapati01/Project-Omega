"""Run existing ingestion/API services inside a scoped cloud worker job."""
import asyncio
import importlib
import io
import json
import time
from uuid import UUID
from fastapi import HTTPException, UploadFile
from app.core.tenant import Scope, current_scope
from app.services import cloud_db, cloud_storage, jobs

HANDLERS = {
    "videos": ("videos", "process_video", "VideoProcessRequest"),
    "instagram": ("instagram", "process_instagram", "InstagramRequest"),
    "pdf": ("pdf", "process_pdf", None),
    "documents": ("documents", "process_document", None),
    "audio": ("audio", "process_audio", None),
    "web": ("web", "process_web", "WebRequest"),
    "chat": ("chat", "chat", "ChatRequest"),
    "search": ("search", "search", "SearchRequest"),
}


def authorize(envelope: dict) -> Scope:
    owner = Scope(**envelope)
    owner.envelope()
    UUID(owner.tenant_id)
    UUID(owner.user_id)
    job = jobs.raw(owner.job_id)
    if any(job[k] != v for k, v in owner.envelope().items()) or job["status"] != "processing":
        raise PermissionError("Invalid job ownership")
    if not cloud_db.member(owner.tenant_id, owner.user_id):
        raise PermissionError("Membership revoked")
    return owner


async def execute(job: dict):
    module, handler, schema = HANDLERS[job["job_type"]]
    api = importlib.import_module("app.api." + module)
    if schema:
        result = await getattr(api, handler)(getattr(api, schema)(**job["payload"]))
    else:
        payload = job["payload"]
        data = await asyncio.to_thread(cloud_storage.get, payload["object"])
        upload = UploadFile(io.BytesIO(data), filename=payload["filename"])
        try:
            result = await getattr(api, handler)(upload)
        finally:
            await upload.close()
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else result


def classify(exc: Exception) -> dict:
    import httpx
    from pydantic import ValidationError
    from app.services.modal_client import WorkerUnavailable
    cause = exc
    transient = False
    while cause:
        if isinstance(cause, (WorkerUnavailable, httpx.TransportError, ConnectionError, TimeoutError)):
            transient = True
        cause = cause.__cause__
    invalid = isinstance(exc, (ValueError, PermissionError, ValidationError))
    if isinstance(exc, HTTPException):
        invalid = exc.status_code < 500 and exc.status_code not in (408, 429)
    if isinstance(exc, httpx.HTTPStatusError):
        invalid = exc.response.status_code < 500 and exc.response.status_code not in (408, 429)
    if transient:
        invalid = False
    return {"error_code": "INVALID_INPUT_OR_ACCESS" if invalid else "PROCESSING_FAILED",
            "message": "Unable to process this request." if invalid else "Processing temporarily unavailable.",
            "retryable": not invalid}


class _PgResourceLock:
    """Expose the Redis lock's acquire/release surface over PG advisory locks."""

    def __init__(self, tenant_id: str, resource_id: str):
        from app.services import cloud_db

        self._cm = cloud_db.resource_lock(tenant_id, resource_id)
        self._entered = False

    def acquire(self) -> bool:
        try:
            self._cm.__enter__()
        except ConnectionError:
            return False
        self._entered = True
        return True

    def release(self) -> None:
        if self._entered:
            self._entered = False
            self._cm.__exit__(None, None, None)


async def run(job_id: str):
    from app.core.logging import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    try:
        job, lease = jobs.claim(job_id)
    except (PermissionError, KeyError):
        return
    owner = Scope(**{k: job[k] for k in ("tenant_id", "user_id", "job_id", "resource_id")})
    context_token = current_scope.set(owner)
    if job["status"] != "processing":
        try:
            cloud_db.save_result(jobs.public(job))
        finally:
            current_scope.reset(context_token)
        return
    started = time.monotonic()
    # Serialize ingestion of the same resource across separate job IDs.
    if jobs._pg():
        lock = _PgResourceLock(owner.tenant_id, owner.resource_id)
    else:
        lock = jobs.client().lock(f"mindmesh:resource:{owner.tenant_id}:{owner.resource_id}", timeout=jobs.LEASE, blocking_timeout=1)
    acquired = False
    try:
        authorize(owner.envelope())
        logger.info(json.dumps({"worker": "processing", "operation": job["job_type"], "status": "processing"}))
        acquired = lock.acquire()
        if not acquired:
            raise ConnectionError("Resource busy")
        result = await execute(job)
        # Persist result before committing Redis terminal status; retry is idempotent.
        cloud_db.save_result({**jobs.public(job), "status": "completed", "result": result})
        job = jobs.finish(job_id, lease, result=result)
    except Exception as exc:
        job = jobs.finish(job_id, lease, error=classify(exc))
        if job["status"] == "failed":
            cloud_db.save_result(jobs.public(job))
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass
        logger.info(json.dumps({**owner.envelope(), "worker": "processing", "operation": job["job_type"],
            "status": job["status"], "duration_ms": round((time.monotonic()-started)*1000),
            "error": (job.get("error") or {}).get("error_code")}))
        current_scope.reset(context_token)
