"""PostgreSQL-backed job lifecycle store for JOB_BACKEND=postgres|gcp.

Same record shape and function signatures as the Redis implementation in
``app.services.jobs`` (float epoch timestamps, identical status machine),
but every state lives in the ``mm_jobs`` table so no Redis server is needed:

* ``create`` inserts a queued row; idempotency keys derive deterministic
  UUIDs exactly like the Redis backend, with fingerprint comparison.
* ``claim``/``finish``/``cancel``/``replay`` run inside a row-locked
  transaction (``SELECT ... FOR UPDATE``), which replaces Redis WATCH
  pipelines and the ``mindmesh:resource:`` lock.
* ``claim_next`` atomically picks the next due job (``FOR UPDATE SKIP
  LOCKED``) for poll-mode workers and crash recovery.
* ``reconcile`` requeues jobs whose lease expired without a finish and
  reports queue/DLQ depth for metrics.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from app.core import metrics
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.tenant import scope
from app.services import cloud_db
from app.services.jobs import LEASE, TERMINAL, QuotaExceeded

logger = get_logger(__name__)

_REQUEUE_SLACK_SECONDS = 300

_COLUMNS = (
    "job_id, tenant_id, user_id, resource_id, job_type, payload, fingerprint,"
    " status, attempts, lease, EXTRACT(EPOCH FROM next_at) AS next_at,"
    " result, error, EXTRACT(EPOCH FROM created_at) AS created_at"
)


def _row_to_job(row) -> dict:
    job = {
        "job_id": str(row[0]),
        "tenant_id": str(row[1]),
        "user_id": str(row[2]),
        "resource_id": row[3],
        "job_type": row[4],
        "payload": row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}"),
        "fingerprint": row[6],
        "status": row[7],
        "attempts": row[8],
        "created_at": float(row[13]),
    }
    if row[9] is not None:
        job["lease"] = row[9]
    if row[10] is not None:
        job["next_at"] = float(row[10])
    if row[11] is not None:
        job["result"] = row[11] if isinstance(row[11], dict) else json.loads(row[11])
    if row[12] is not None:
        job["error"] = row[12] if isinstance(row[12], dict) else json.loads(row[12])
    return job


def _coerce_job_id(job_id: str) -> str:
    try:
        return str(uuid.UUID(str(job_id)))
    except (ValueError, AttributeError, TypeError):
        raise KeyError("Job not found") from None


def raw(job_id: str) -> dict:
    job_id = _coerce_job_id(job_id)
    with cloud_db.connect() as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM public.mm_jobs WHERE job_id=%s", (job_id,)).fetchone()
    if row is None:
        raise KeyError("Job not found")
    return _row_to_job(row)


def owned(job_id: str) -> dict:
    job = raw(job_id)
    owner = scope()
    if job["tenant_id"] != owner.tenant_id or job["user_id"] != owner.user_id:
        metrics.inc("cross_tenant_denied_total", resource="job")
        logger.warning(
            "cross_tenant_denied resource=job job_id=%s requester_tenant=%s owner_tenant=%s",
            job_id, owner.tenant_id, job["tenant_id"],
        )
        raise KeyError("Job not found")
    return job


def create(job_type: str, payload: dict, resource_id: str, idempotency_key: str = "") -> dict:
    owner = scope()
    settings = get_settings()
    fingerprint = hashlib.sha256(json.dumps([job_type, payload], sort_keys=True).encode()).hexdigest()
    identity = f"{owner.tenant_id}:{owner.user_id}:{idempotency_key}"
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity)) if idempotency_key else str(uuid.uuid4())
    from psycopg.types.json import Jsonb
    with cloud_db.connect() as conn:
        with conn.cursor() as cur:
            # Serialize a tenant's new-job admission. The previous Redis-only
            # quota path skipped all idempotency-keyed requests, allowing an
            # attacker to mint fresh keys and bypass the daily limit.
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (owner.tenant_id,))
            if idempotency_key:
                cur.execute("SELECT fingerprint FROM public.mm_jobs WHERE job_id=%s", (job_id,))
                existing = cur.fetchone()
                if existing is not None:
                    if existing[0] != fingerprint:
                        raise ValueError("Idempotency key already used for another request")
                    conn.commit()
                    metrics.inc("jobs_enqueued_total", type=job_type)
                    return raw(job_id)
            if settings.max_jobs_per_tenant_per_day:
                cur.execute(
                    "SELECT count(*) FROM public.mm_jobs WHERE tenant_id=%s AND created_at >= date_trunc('day', now())",
                    (owner.tenant_id,),
                )
                used = cur.fetchone()[0]
                if used >= settings.max_jobs_per_tenant_per_day:
                    metrics.inc("quota_rejected_total", kind="jobs")
                    raise QuotaExceeded(f"Daily job quota reached ({used})")
            cur.execute(
                """INSERT INTO public.mm_jobs(job_id, tenant_id, user_id, resource_id,
                       job_type, payload, fingerprint, status, attempts)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',0)
                   ON CONFLICT (job_id) DO NOTHING
                   RETURNING fingerprint""",
                (job_id, owner.tenant_id, owner.user_id, resource_id, job_type, Jsonb(payload), fingerprint),
            )
            inserted = cur.fetchone()
            if inserted is None:
                cur.execute("SELECT fingerprint FROM public.mm_jobs WHERE job_id=%s", (job_id,))
                existing = cur.fetchone()
                if existing is None or existing[0] != fingerprint:
                    raise ValueError("Idempotency key already used for another request")
                conn.commit()
                metrics.inc("jobs_enqueued_total", type=job_type)
                return raw(job_id)
            conn.commit()
    metrics.inc("jobs_enqueued_total", type=job_type)
    return raw(job_id)


def _transition(job_id: str, update) -> dict:
    """Run update(job) inside a row-locked transaction, then persist."""
    from psycopg.types.json import Jsonb
    job_id = _coerce_job_id(job_id)
    with cloud_db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_COLUMNS} FROM public.mm_jobs WHERE job_id=%s FOR UPDATE", (job_id,))
            row = cur.fetchone()
            if row is None:
                raise KeyError("Job not found")
            job = _row_to_job(row)
            update(job)
            cur.execute(
                """UPDATE public.mm_jobs
                   SET status=%s, attempts=%s, lease=%s,
                       next_at=to_timestamp(%s), result=%s, error=%s,
                       dlq=%s, updated_at=now()
                   WHERE job_id=%s""",
                (job["status"], job.get("attempts", 0), job.get("lease"),
                 job.get("next_at", time.time()),
                 Jsonb(job["result"]) if job.get("result") is not None else None,
                 Jsonb(job["error"]) if job.get("error") is not None else None,
                 bool(job.get("status") == "failed"),
                 job_id),
            )
            conn.commit()
    return raw(job_id)


def claim(job_id: str) -> tuple[dict, str]:
    token = str(uuid.uuid4())

    def update(job):
        if job["status"] in TERMINAL or (job["status"] == "processing" and job["next_at"] > time.time()):
            raise PermissionError("Job already claimed or finished")
        if job["attempts"] >= 3:
            job.update(status="failed", error={"error_code": "RETRY_EXHAUSTED", "message": "Processing did not finish.", "retryable": False})
            return
        job.update(status="processing", attempts=job["attempts"] + 1, lease=token, next_at=time.time() + LEASE)

    return _transition(job_id, update), token


def claim_next() -> tuple[dict | None, str]:
    """Atomically claim the next due queued job (poll-mode workers)."""
    from psycopg.types.json import Jsonb
    token = str(uuid.uuid4())
    with cloud_db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id FROM public.mm_jobs WHERE status='queued' AND next_at <= now()"
                " ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED",
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return None, ""
            job_id = str(row[0])
            cur.execute(f"SELECT {_COLUMNS} FROM public.mm_jobs WHERE job_id=%s FOR UPDATE", (job_id,))
            job = _row_to_job(cur.fetchone())
            if job["attempts"] >= 3:
                job.update(status="failed", error={"error_code": "RETRY_EXHAUSTED", "message": "Processing did not finish.", "retryable": False})
            else:
                job.update(status="processing", attempts=job["attempts"] + 1, lease=token, next_at=time.time() + LEASE)
            cur.execute(
                """UPDATE public.mm_jobs
                   SET status=%s, attempts=%s, lease=%s,
                       next_at=to_timestamp(%s), error=%s,
                       dlq=%s, updated_at=now()
                   WHERE job_id=%s""",
                (job["status"], job.get("attempts", 0), job.get("lease"),
                 job.get("next_at", time.time()),
                 Jsonb(job["error"]) if job.get("error") is not None else None,
                 bool(job.get("status") == "failed"), job_id),
            )
            conn.commit()
    return raw(job_id), token


def peek_due() -> str | None:
    """Return the next due queued job id without claiming it.

    Poll-mode workers fork a child per job and the child claims inside
    run() — identical to the Redis worker loop, so duplicate deliveries and
    crashed children resolve through the same lease/reconcile path.
    """
    with cloud_db.connect() as conn:
        row = conn.execute(
            "SELECT job_id FROM public.mm_jobs WHERE status='queued' AND next_at <= now()"
            " ORDER BY next_at LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else None


def finish(job_id: str, token: str, result=None, error=None) -> dict:
    def update(job):
        if job.get("lease") != token or job["status"] != "processing":
            raise PermissionError("Stale worker lease")
        if error and error["retryable"] and job["attempts"] < 3:
            job.update(status="queued", error=error, next_at=time.time() + 30 * job["attempts"])
        else:
            job.update(status="failed" if error else "completed", result=result, error=error)
    outcome = _transition(job_id, update)
    metrics.inc("jobs_finished_total", status=outcome["status"])
    return outcome


def cancel(job_id: str) -> dict:
    owned(job_id)

    def update(job):
        if job["status"] != "queued":
            raise ValueError("Only queued jobs can be cancelled")
        job["status"] = "cancelled"
    return _transition(job_id, update)


def replay(job_id: str) -> dict:
    """Operator action: move a dead-lettered job back onto the queue."""

    def update(job):
        if job["status"] != "failed":
            raise ValueError("Only failed jobs can be replayed")
        job.update(status="queued", attempts=0, error=None, next_at=time.time())
    job = _transition(job_id, update)
    metrics.inc("jobs_replayed_total")
    return job


def reconcile() -> dict:
    """Requeue jobs whose lease expired without a finish. Returns counts."""
    stats = {"orphans_pruned": 0, "terminal_pruned": 0, "dlq_size": 0}
    with cloud_db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.mm_jobs SET status='queued', lease=NULL, next_at=now(), updated_at=now()
                   WHERE status='processing'
                     AND next_at < now() - make_interval(secs => %s)
                   RETURNING job_id""",
                (LEASE + _REQUEUE_SLACK_SECONDS,),
            )
            requeued = cur.fetchall()
            if requeued:
                stats["requeued"] = len(requeued)
                for (job_id,) in requeued:
                    logger.warning("requeued_stale_job job_id=%s", job_id)
            cur.execute("SELECT count(*) FROM public.mm_jobs WHERE status NOT IN ('completed','failed','cancelled')")
            queue_depth = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM public.mm_jobs WHERE dlq")
            stats["dlq_size"] = cur.fetchone()[0]
            conn.commit()
    metrics.set_gauge("jobs_queue_depth", float(queue_depth))
    metrics.set_gauge("jobs_dlq_depth", float(stats["dlq_size"]))
    return stats
