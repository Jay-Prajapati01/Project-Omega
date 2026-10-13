"""Cloud facade: authenticate, validate, stage inputs, queue, and report status."""
import asyncio
import hashlib
import importlib
import json
import time
from pathlib import PurePath
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from app.core import metrics
from app.core.config import get_settings
from app.core.filesignature import FileSignatureError, validate_signature
from app.core.logging import get_logger
from app.core.ratelimit import quota_hit
from app.core.uploads import discard_spooled, read_upload, spool_upload
from app.core.tenant import scope
from app.services import jobs, cloud_storage
from app.services.job_runner import HANDLERS
from app.services.sse import sse

logger = get_logger(__name__)
router = APIRouter()
_upload_slots = asyncio.Semaphore(get_settings().max_concurrent_heavy_tasks)

_UPLOAD_SUFFIXES = {"pdf": {".pdf"}, "documents": {".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".markdown"},
                    "audio": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".webm"}}


def _check_upload_head(kind: str, filename: str) -> str:
    suffix = PurePath(filename).suffix.lower()
    if suffix not in _UPLOAD_SUFFIXES[kind]:
        raise HTTPException(400, "Unsupported file format")
    return suffix


def _charge_upload_quota(size: int) -> None:
    settings = get_settings()
    allowed_quota, _used = quota_hit(
        scope().tenant_id, "upload_bytes", size, settings.max_upload_bytes_per_tenant_per_day)
    if not allowed_quota:
        metrics.inc("quota_rejected_total", kind="upload_bytes")
        raise HTTPException(429, "Daily upload quota reached",
                            headers={"Retry-After": "3600"})


async def stage_file(kind: str, request: Request) -> tuple[dict, str]:
    async with request.form() as form:
        file = form.get("file")
        if file is None or not getattr(file, "filename", None):
            raise HTTPException(400, "File required")
        filename = PurePath(file.filename.replace("\\", "/")).name
        suffix = _check_upload_head(kind, filename)
        if get_settings().mindmesh_execution_mode == "cloud":
            return await _stage_file_spooled(kind, filename, suffix, file)
        data = await read_upload(file)
    if not data:
        raise HTTPException(400, "Empty file")
    # Content must match the extension before anything is staged (audit P0-10).
    try:
        validate_signature(filename, data)
    except FileSignatureError as exc:
        metrics.inc("upload_rejected_total", reason="signature")
        raise HTTPException(400, str(exc)) from None
    # Per-tenant daily upload quota (audit P0-9): reject BEFORE storing bytes.
    _charge_upload_quota(len(data))
    resource = hashlib.sha256(data).hexdigest()
    path = f"inputs/{resource}{suffix}"
    await asyncio.to_thread(cloud_storage.put, path, data)
    payload = {"object": path, "filename": filename}
    return payload, resource


async def _stage_file_spooled(kind: str, filename: str, suffix: str, file) -> tuple[dict, str]:
    """Cloud intake: spool to ephemeral disk, then stream to storage.

    The quota is charged from the spooled size before any byte reaches
    Supabase; the temp file is always removed, including on failure.
    """
    del kind  # suffix allow-list already enforced by the caller
    spooled, size = await spool_upload(file)
    try:
        if size == 0:
            raise HTTPException(400, "Empty file")
        _charge_upload_quota(size)
        with open(spooled, "rb") as handle:
            data = handle.read()
        try:
            validate_signature(filename, data)
        except FileSignatureError as exc:
            metrics.inc("upload_rejected_total", reason="signature")
            raise HTTPException(400, str(exc)) from None
        resource = hashlib.sha256(data).hexdigest()
        del data
        path = f"inputs/{resource}{suffix}"
        await asyncio.to_thread(cloud_storage.put_file, path, spooled)
    finally:
        discard_spooled(spooled)
    payload = {"object": path, "filename": filename}
    return payload, resource


async def enqueue_payload(kind: str, incoming: dict, idempotency: str = "") -> dict:
    """Validate and enqueue a JSON job for another authenticated facade."""
    module, _, schema = HANDLERS[kind]
    from app.services.commerce import reserve
    feature = {"videos": "youtube", "instagram": "instagram", "pdf": "pdf", "documents": "documents", "audio": "audio", "web": "web", "search": "search", "chat": "chat"}.get(kind)
    if feature:
        reserve(feature, idempotency)
    staged_object: str | None = None
    if schema is None:
        raise HTTPException(400, "This endpoint accepts URLs only")
    api = importlib.import_module("app.api." + module)
    try:
        payload = getattr(api, schema).model_validate(incoming).model_dump(mode="json")
    except (ValidationError, ValueError):
        raise HTTPException(422, "Invalid request") from None
    if kind == "chat" and payload.get("conversation_id"):
        resource = "conversation:" + payload["conversation_id"]
    else:
        resource = hashlib.sha256(json.dumps([kind, payload], sort_keys=True).encode()).hexdigest()
    if len(idempotency) > 128:
        raise HTTPException(400, "Idempotency key too long")
    try:
        job = await asyncio.to_thread(jobs.create, kind, payload, resource, idempotency)
    except jobs.QuotaExceeded as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "86400"}) from None
    except Exception:
        # Never leave an orphaned staged object behind when enqueue fails.
        if staged_object:
            try:
                await asyncio.to_thread(cloud_storage.delete, staged_object)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.warning("staged object cleanup failed object=%s err=%s", staged_object, cleanup_exc)
        raise
    if get_settings().job_backend == "gcp":
        # Schedule authenticated dispatch; never fails the request — when
        # Cloud Tasks is unreachable the row stays queued for poll-mode.
        from app.services import cloud_tasks

        await asyncio.to_thread(cloud_tasks.enqueue_best_effort, job["job_id"])
    return job


async def enqueue(kind: str, request: Request):
    module, _, schema = HANDLERS[kind]
    if schema is None:
        async with _upload_slots:
            payload, resource = await stage_file(kind, request)
        idempotency = request.headers.get("Idempotency-Key", "")
        if len(idempotency) > 128:
            raise HTTPException(400, "Idempotency key too long")
        try:
            return await asyncio.to_thread(jobs.create, kind, payload, resource, idempotency)
        except jobs.QuotaExceeded as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "86400"}) from None
    return await enqueue_payload(kind, await request.json(), request.headers.get("Idempotency-Key", ""))


def endpoint(kind: str, stream: bool):
    async def submit(request: Request):
        job = await enqueue(kind, request)
        if not stream:
            return JSONResponse(jobs.public(job), status_code=202, headers={"Location": f"{get_settings().api_prefix}/jobs/{job['job_id']}"})

        async def events():
            yield sse("queued", jobs.public(job))
            yield sse("step_start", {"step": 1, "total_steps": 1, "name": "Cloud processing"})
            deadline = time.monotonic() + get_settings().sse_max_wait_seconds
            while True:
                if time.monotonic() > deadline:
                    # Honest terminal state instead of an infinite spinner.
                    metrics.inc("sse_deadline_exceeded_total")
                    yield sse("error", {"error": "Processing is taking longer than expected. "
                                                 "Check the job status page for the final result.",
                                        "job_id": job["job_id"]})
                    return
                try:
                    latest = await asyncio.to_thread(jobs.owned, job["job_id"])
                except KeyError:
                    yield sse("error", {"error": "Job no longer exists", "job_id": job["job_id"]})
                    return
                if latest["status"] in jobs.TERMINAL:
                    if latest["status"] == "completed":
                        result = latest["result"]
                        if kind == "chat":
                            yield f"data: {json.dumps({'type': 'token', 'content': result['answer']})}\n\n"
                            yield f"data: {json.dumps({'type': 'done', **result})}\n\n"
                        else:
                            yield sse("step_complete", {"step": 1})
                            yield sse("complete", result)
                    else:
                        message = (latest.get("error") or {}).get("message", "Job cancelled")
                        yield sse("error", {"error": message, "job_id": job["job_id"]})
                    return
                yield ": waiting\n\n"
                await asyncio.sleep(2)
        return StreamingResponse(events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Job-ID": job["job_id"]})
    return submit


for _kind in HANDLERS:
    _base = f"/{_kind}" + ("/process" if _kind in {"pdf", "documents", "audio", "videos", "web", "instagram"} else "")
    router.add_api_route(_base, endpoint(_kind, False), methods=["POST"], name=f"queue_{_kind}")
    if _kind not in {"search", "compare"}:
        router.add_api_route(_base + "/stream", endpoint(_kind, True), methods=["POST"], name=f"stream_{_kind}")


@router.get("/jobs/{job_id}")
async def status(job_id: str):
    try:
        return jobs.public(await asyncio.to_thread(jobs.owned, job_id))
    except (KeyError, ValueError):
        raise HTTPException(404, "Job not found") from None


@router.delete("/jobs/{job_id}")
async def cancel(job_id: str):
    try:
        return jobs.public(await asyncio.to_thread(jobs.cancel, job_id))
    except KeyError:
        raise HTTPException(404, "Job not found") from None
    except ValueError:
        raise HTTPException(409, "Only queued jobs can be cancelled") from None
