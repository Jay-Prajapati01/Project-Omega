"""Private worker. The active job backend (Redis or Postgres) supplies authoritative ownership; no public job API.

Run one job in a child process with a hard deadline shorter than the Redis
lease. A killed process leaves the lease for existing reconciliation/retries.
"""
import asyncio
import multiprocessing
import time

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


def execute(job_id: str):
    from app.services.job_runner import run
    asyncio.run(run(job_id))


def main():
    cfg = get_settings()
    if cfg.mindmesh_execution_mode != "cloud" or not cfg.worker_process:
        raise RuntimeError("Worker requires cloud mode and WORKER_PROCESS=true")
    configure_logging()
    logger = get_logger(__name__)
    from app.services import jobs
    use_pg = jobs._pg()
    jobs_pg = None
    if use_pg:
        from app.services import jobs_pg as _jobs_pg

        jobs_pg = _jobs_pg
    context = multiprocessing.get_context("spawn")
    poll_seconds = cfg.worker_poll_seconds
    reconciled = 0.0
    while True:
        try:
            if time.monotonic() - reconciled >= 60:
                jobs.reconcile()
                reconciled = time.monotonic()
            if use_pg:
                # Poll Postgres; the forked child claims inside run(), exactly
                # like the Redis loop, so crashes resolve through leases.
                job_id = jobs_pg.peek_due()
                if job_id is None:
                    time.sleep(poll_seconds)
                    continue
            else:
                due = jobs.client().zrangebyscore(jobs.QUEUE, 0, time.time(), start=0, num=1)
                if not due:
                    time.sleep(poll_seconds)
                    continue
                job_id = due[0]
            process = context.Process(target=execute, args=(job_id,))
            process.start()
            process.join(timeout=3600)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        except Exception:
            logger.warning("Worker iteration deferred")
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
