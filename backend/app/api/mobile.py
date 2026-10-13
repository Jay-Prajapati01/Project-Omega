"""Fast acknowledgement facade for the native companion's shared URLs."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from urllib.parse import urlsplit

from app.core.config import get_settings

router = APIRouter(prefix="/mobile", tags=["mobile"])


class QuickSaveRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


def _kind(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise HTTPException(422, "A valid http or https URL is required")
    if host in {"youtu.be", "youtube.com"} or host.endswith(".youtube.com"):
        return "videos"
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    raise HTTPException(422, "Only YouTube and Instagram links can be saved from the companion app")


@router.post("/quick-saves", status_code=202)
async def quick_save(payload: QuickSaveRequest, request: Request):
    idempotency = request.headers.get("Idempotency-Key", "")
    if not idempotency or len(idempotency) > 128:
        raise HTTPException(400, "A stable Idempotency-Key is required")
    kind = _kind(payload.url)
    from app.services.commerce import CommerceError, reserve, provider_mode
    resource_notice = {"provider": provider_mode(), "feature": {"videos": "youtube", "instagram": "instagram", "web": "web"}[kind]}
    if get_settings().mindmesh_execution_mode in {"modal", "cloud"}:
        try:
            resource_notice = reserve(resource_notice["feature"], idempotency)
        except CommerceError as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
        from app.api.cloud_jobs import enqueue_payload
        job = await enqueue_payload(kind, {"url": payload.url}, idempotency)
        return {"item_id": job["resource_id"], "job_id": job["job_id"], "status": job["status"], "resource_notice": resource_notice}
    from app.services import mobile_saves
    job, is_new = mobile_saves.create(kind, payload.url, idempotency)
    if is_new:
        try:
            resource_notice = reserve(resource_notice["feature"], idempotency)
        except CommerceError as exc:
            mobile_saves.remove(job["job_id"])
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
    if job["status"] == "queued":
        mobile_saves.schedule(job["job_id"])
    return {"item_id": job["job_id"], "job_id": job["job_id"], "status": job["status"], "resource_notice": resource_notice}


@router.get("/quick-saves/{job_id}")
async def quick_save_status(job_id: str):
    if get_settings().mindmesh_execution_mode in {"modal", "cloud"}:
        from app.services import jobs
        try:
            return jobs.public(jobs.owned(job_id))
        except (KeyError, ValueError):
            raise HTTPException(404, "Save not found") from None
    from app.services import mobile_saves
    try:
        job = mobile_saves.recover_orphaned(job_id)
        if job["status"] == "queued":
            mobile_saves.schedule(job_id)
        return job
    except KeyError:
        raise HTTPException(404, "Save not found") from None
