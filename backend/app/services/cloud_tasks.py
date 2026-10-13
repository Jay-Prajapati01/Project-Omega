"""Google Cloud Tasks dispatch for JOB_BACKEND=gcp.

Flow: API creates the Postgres job row, then schedules an authenticated
Cloud Tasks HTTP task targeting the private dispatcher service. The
dispatcher (also in this repo) launches one Cloud Run Job execution per
task. Cloud Tasks retries only the *dispatch*; the job row itself tracks
real completion, and duplicate deliveries resolve through jobs.claim().

Credentials use the workload identity (metadata server) — no service-account
keys are stored anywhere. When the metadata server is unreachable (local
development, CI) enqueue raises TasksUnavailable and the caller must leave
the job queued for a poll-mode worker instead of failing the request.
"""
from __future__ import annotations

import json

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
_TASKS_SCOPE = "https://www.googleapis.com/auth/cloud-tasks"


class TasksUnavailable(RuntimeError):
    """Cloud Tasks cannot be reached from this environment."""


def _access_token() -> str:
    try:
        resp = httpx.get(
            _METADATA_TOKEN_URL,
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as exc:  # noqa: BLE001 — metadata absent outside GCP
        raise TasksUnavailable(f"GCP metadata server unreachable: {exc}") from None


def enqueue(job_id: str) -> str:
    """Schedule dispatch of a queued job. Returns the Cloud Tasks task name."""
    settings = get_settings()
    parent = (
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}"
        f"/queues/{settings.cloud_tasks_queue}"
    )
    body = {
        "task": {
            "httpRequest": {
                "httpMethod": "POST",
                "url": settings.cloud_tasks_dispatcher_url.rstrip("/") + f"/dispatch/{job_id}",
                "oidcToken": {"serviceAccountEmail": settings.cloud_tasks_service_account},
                "headers": {"X-Dispatch-Secret": settings.cloud_tasks_dispatch_secret},
            }
        }
    }
    url = f"https://cloudtasks.googleapis.com/v1/{parent}/tasks"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Cloud Tasks returned {resp.status_code}: {resp.text[:300]}")
        name = resp.json().get("name", "")
    except TasksUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TasksUnavailable(f"Cloud Tasks enqueue failed: {exc}") from None
    logger.info(json.dumps({"cloud_tasks_enqueued": name, "job_id": job_id}))
    return name


def enqueue_best_effort(job_id: str) -> str | None:
    """Enqueue, returning None (job stays queued for poll-mode) when Tasks is unreachable."""
    try:
        return enqueue(job_id)
    except TasksUnavailable as exc:
        logger.warning("Cloud Tasks unavailable; job %s left queued for poll-mode worker: %s", job_id, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cloud Tasks enqueue deferred for job %s: %s", job_id, exc)
        return None
