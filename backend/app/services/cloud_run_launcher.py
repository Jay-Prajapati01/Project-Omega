"""Launch Cloud Run Job executions from the private dispatcher service.

Uses the workload identity (metadata server access token) against the Cloud
Run Admin API — no stored keys. A launch failure raises ConnectionError so
job_runner.classify() treats it as transient and the job is requeued with
backoff instead of being marked failed.
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


def _access_token() -> str:
    try:
        resp = httpx.get(_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=5)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as exc:  # noqa: BLE001 — metadata absent outside GCP
        raise ConnectionError(f"GCP metadata server unreachable: {exc}") from None


def launch(job_id: str) -> str:
    """Start one Cloud Run Job execution for job_id. Returns the operation name."""
    settings = get_settings()
    name = (
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}"
        f"/jobs/{settings.cloud_run_job_name}"
    )
    url = f"https://run.googleapis.com/v1/{name}:run"
    body = {
        "overrides": {
            "containerOverrides": [{"env": [{"name": "MINDMESH_JOB_ID", "value": job_id}]}],
            "taskCount": 1,
        }
    }
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if resp.status_code >= 400:
            raise ConnectionError(f"Cloud Run Job launch returned {resp.status_code}: {resp.text[:300]}")
        operation = resp.json().get("name", "")
    except ConnectionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConnectionError(f"Cloud Run Job launch failed: {exc}") from None
    logger.info(json.dumps({"cloud_run_launched": operation, "job_id": job_id}))
    return operation
