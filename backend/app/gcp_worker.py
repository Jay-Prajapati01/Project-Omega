"""Single-job Cloud Run Job entrypoint (run-to-completion).

The dispatcher injects MINDMESH_JOB_ID per execution; the process runs one
job through job_runner.run() and exits so Cloud Run Job billing stops.
Duplicate deliveries (two executions for one job) resolve inside run():
only the first claim wins and the loser exits 0 without touching data.
"""
from __future__ import annotations

import asyncio
import os


def main() -> int:
    from app.core.config import get_settings

    cfg = get_settings()
    if cfg.mindmesh_execution_mode != "cloud" or cfg.job_backend not in {"postgres", "gcp"}:
        raise RuntimeError("GCP worker requires cloud mode and a Postgres job backend")
    job_id = os.environ.get("MINDMESH_JOB_ID", "")
    if not job_id:
        raise RuntimeError("MINDMESH_JOB_ID is required")
    from app.core.logging import configure_logging

    configure_logging()
    from app.services import job_runner

    asyncio.run(job_runner.run(job_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
