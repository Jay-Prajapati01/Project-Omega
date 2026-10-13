"""Public contact-form intake — reachable without an account.

Submissions are stored in the Supabase `contact_submissions` table through
the service-role REST endpoint (server-side writes only; browsers never talk
to the table directly). The REST path works from any container because it
rides HTTPS — the project's direct Postgres endpoint is IPv6-only. When
Supabase is not configured — offline dev or tests — the message falls back to
a JSONL file under the data directory so the form still works everywhere. The
outer IP rate limiter and body-size guard apply as usual; the auth middleware
exempts exactly this path (see CloudAuthMiddleware).
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["contact"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
ALLOWED_TOPICS = ("General", "Account support", "Partnership", "Bug / feedback")
MAX_STORE_BYTES = 5 * 1024 * 1024  # rotate so a spam run cannot fill the disk


class ContactSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    company: str | None = Field(default=None, max_length=120)
    topic: str = Field(default="General", max_length=40)
    message: str = Field(min_length=10, max_length=2000)
    website: str = Field(default="", max_length=200)

    @field_validator("name", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("must be a valid email address")
        return value

    @field_validator("topic")
    @classmethod
    def allowed_topic(cls, value: str) -> str:
        if value not in ALLOWED_TOPICS:
            raise ValueError(f"topic must be one of: {', '.join(ALLOWED_TOPICS)}")
        return value

    @field_validator("company")
    @classmethod
    def strip_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


def _store_path() -> Path:
    return Path(get_settings().data_dir) / "contact_submissions.jsonl"


def _append(payload: dict) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > MAX_STORE_BYTES:
        path.replace(path.with_suffix(".jsonl.1"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _insert_supabase(payload: dict) -> None:
    """Insert one row through the Supabase REST API with the service-role key."""
    settings = get_settings()
    response = httpx.post(
        f"{settings.supabase_url}/rest/v1/contact_submissions",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "name": payload["name"],
            "email": payload["email"],
            "company": payload["company"],
            "topic": payload["topic"],
            "message": payload["message"],
            "received_at": payload["received_at"],
        },
        timeout=10,
    )
    response.raise_for_status()


def _store_supabase(payload: dict) -> bool:
    """Persist through Supabase; False triggers the file fallback."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return False
    try:
        _insert_supabase(payload)
        return True
    except Exception as exc:  # noqa: BLE001 — the form must survive an outage
        logger.warning("Supabase contact insert failed (%s)", type(exc).__name__)
        return False


def _persist(payload: dict) -> None:
    if _store_supabase(payload):
        return
    if get_settings().environment == "production":
        raise HTTPException(status_code=503, detail="Contact submissions are temporarily unavailable")
    _append(payload)


@router.post("/contact", status_code=202)
async def submit_contact(submission: ContactSubmission) -> dict[str, str]:
    # Honeypot: quietly accept automated submissions without storing or alerting.
    if submission.website.strip():
        return {"status": "received"}
    payload = submission.model_dump()
    payload.pop("website", None)
    payload["received_at"] = datetime.now(timezone.utc).isoformat()
    try:
        await asyncio.to_thread(_persist, payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Contact submission persistence failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Contact submissions are temporarily unavailable") from exc
    logger.info("Contact submission received (%s)", submission.topic)
    from app.core import metrics

    metrics.inc("contact_submissions_total", topic=submission.topic)
    return {"status": "received"}
