"""Redis-backed durable queue with atomic transitions and bounded crash recovery.

Durability model:
* Job records live in Redis with a TTL; terminal results are mirrored to
  Postgres (mm_job_results) by the worker.
* Permanently failed jobs are moved to a dead-letter queue (DLQ) so an
  operator can inspect and replay them.
* ``reconcile()`` prunes queue entries whose job record vanished, drops
  terminal jobs that are still scheduled, and reports DLQ depth — run it
  from the dispatcher loop so Redis drift self-heals.
"""
import hashlib
import json
import time
import uuid
from functools import lru_cache

from redis import Redis, WatchError

from app.core import metrics
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import quota_hit
from app.core.tenant import scope

logger = get_logger(__name__)

QUEUE = "mindmesh:jobs:due"
DLQ = "mindmesh:jobs:dlq"
LEASE = 3900  # Must exceed Modal's 3600-second hard timeout.
TERMINAL = {"completed", "failed", "cancelled"}


def _pg() -> bool:
    """True when job rows live in Postgres (JOB_BACKEND=postgres|gcp).

    The Redis implementation below is kept byte-for-byte for the legacy
    redis backend and the existing test suite; every public function
    delegates to app.services.jobs_pg when the Postgres backend is active.
    """
    return get_settings().job_backend in {"postgres", "gcp"}


def _delegate(name: str, *args, **kwargs):
    from app.services import jobs_pg

    return getattr(jobs_pg, name)(*args, **kwargs)


@lru_cache
def client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True,
                          socket_timeout=15, socket_connect_timeout=10)


def key(job_id: str) -> str:
    return "mindmesh:job:" + str(uuid.UUID(job_id))


def raw(job_id: str) -> dict:
    if _pg():
        return _delegate("raw", job_id)
    data = client().get(key(job_id))
    if not data:
        raise KeyError("Job not found")
    return json.loads(data)


def owned(job_id: str) -> dict:
    if _pg():
        return _delegate("owned", job_id)
    job = raw(job_id)
    owner = scope()
    if job["tenant_id"] != owner.tenant_id or job["user_id"] != owner.user_id:
        # Existence must not leak across tenants, but the attempt is audited.
        metrics.inc("cross_tenant_denied_total", resource="job")
        logger.warning(
            "cross_tenant_denied resource=job job_id=%s requester_tenant=%s owner_tenant=%s",
            job_id, owner.tenant_id, job["tenant_id"],
        )
        raise KeyError("Job not found")
    return job


def public(job: dict) -> dict:
    return {k: job.get(k) for k in ("job_id", "resource_id", "job_type", "status", "attempts", "result", "error")}


def create(job_type: str, payload: dict, resource_id: str, idempotency_key: str = "") -> dict:
    if _pg():
        return _delegate("create", job_type, payload, resource_id, idempotency_key)
    owner = scope()
    settings = get_settings()
    # Daily job quota per tenant: cheap first line of defence against GPU
    # spend storms (audit P0-9). Counted before dedupe so replays of the
    # same idempotency key do not double-charge the quota.
    if idempotency_key == "":
        allowed, used = quota_hit(owner.tenant_id, "jobs", 1, settings.max_jobs_per_tenant_per_day)
        if not allowed:
            metrics.inc("quota_rejected_total", kind="jobs")
            raise QuotaExceeded(f"Daily job quota reached ({used})")
    fingerprint = hashlib.sha256(json.dumps([job_type, payload], sort_keys=True).encode()).hexdigest()
    identity = f"{owner.tenant_id}:{owner.user_id}:{idempotency_key}"
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity)) if idempotency_key else str(uuid.uuid4())
    job = dict(job_id=job_id, tenant_id=owner.tenant_id, user_id=owner.user_id,
               resource_id=resource_id, job_type=job_type, payload=payload,
               fingerprint=fingerprint, status="queued", attempts=0, created_at=time.time())
    r = client()
    while True:
        with r.pipeline() as pipe:
            try:
                pipe.watch(key(job_id))
                old = pipe.get(key(job_id))
                if old:
                    old = json.loads(old)
                    if old["fingerprint"] != fingerprint:
                        raise ValueError("Idempotency key already used for another request")
                    return old
                pipe.multi()
                pipe.set(key(job_id), json.dumps(job), ex=settings.job_ttl_seconds)
                pipe.zadd(QUEUE, {job_id: time.time()})
                pipe.execute()
                metrics.inc("jobs_enqueued_total", type=job_type)
                return job
            except WatchError:
                continue


class QuotaExceeded(ValueError):
    """Daily per-tenant quota exhausted (mapped to 429 by the facade)."""


def transition(job_id: str, update) -> dict:
    r = client()
    while True:
        with r.pipeline() as pipe:
            try:
                pipe.watch(key(job_id))
                value = pipe.get(key(job_id))
                if not value:
                    raise KeyError("Job not found")
                job = json.loads(value)
                update(job)
                pipe.multi()
                pipe.set(key(job_id), json.dumps(job), ex=get_settings().job_ttl_seconds)
                if job["status"] in TERMINAL:
                    pipe.zrem(QUEUE, job_id)
                    if job["status"] == "failed":
                        # Dead-letter every permanent failure for operator replay.
                        pipe.zadd(DLQ, {job_id: time.time()})
                        metrics.inc("jobs_dead_lettered_total")
                    else:
                        pipe.zrem(DLQ, job_id)
                else:
                    pipe.zadd(QUEUE, {job_id: job.get("next_at", time.time())})
                pipe.execute()
                return job
            except WatchError:
                continue


def claim(job_id: str) -> tuple[dict, str]:
    if _pg():
        return _delegate("claim", job_id)
    token = str(uuid.uuid4())
    def update(job):
        if job["status"] in TERMINAL or (job["status"] == "processing" and job["next_at"] > time.time()):
            raise PermissionError("Job already claimed or finished")
        if job["attempts"] >= 3:
            job.update(status="failed", error={"error_code": "RETRY_EXHAUSTED", "message": "Processing did not finish.", "retryable": False})
            return
        job.update(status="processing", attempts=job["attempts"] + 1, lease=token, next_at=time.time() + LEASE)
    return transition(job_id, update), token


def finish(job_id: str, token: str, result=None, error=None) -> dict:
    if _pg():
        return _delegate("finish", job_id, token, result=result, error=error)
    def update(job):
        if job.get("lease") != token or job["status"] != "processing":
            raise PermissionError("Stale worker lease")
        if error and error["retryable"] and job["attempts"] < 3:
            job.update(status="queued", error=error, next_at=time.time() + 30 * job["attempts"])
        else:
            job.update(status="failed" if error else "completed", result=result, error=error)
    outcome = transition(job_id, update)
    metrics.inc("jobs_finished_total", status=outcome["status"])
    return outcome


def cancel(job_id: str) -> dict:
    if _pg():
        return _delegate("cancel", job_id)
    owned(job_id)
    def update(job):
        # Processing may already have durable side effects. Do not promise
        # rollback; terminal jobs must not silently accept a cancel either.
        if job["status"] != "queued":
            raise ValueError("Only queued jobs can be cancelled")
        job["status"] = "cancelled"
    return transition(job_id, update)


def replay(job_id: str) -> dict:
    """Operator action: move a dead-lettered job back onto the queue."""
    if _pg():
        return _delegate("replay", job_id)
    def update(job):
        if job["status"] != "failed":
            raise ValueError("Only failed jobs can be replayed")
        job.update(status="queued", attempts=0, error=None, next_at=time.time())
    job = transition(job_id, update)
    client().zrem(DLQ, job_id)
    metrics.inc("jobs_replayed_total")
    return job


def reconcile() -> dict:
    """Self-heal queue drift. Returns counts for logging/metrics."""
    if _pg():
        return _delegate("reconcile")
    r = client()
    stats = {"orphans_pruned": 0, "terminal_pruned": 0, "dlq_size": 0}
    now = time.time()
    for job_id in r.zrange(QUEUE, 0, -1):
        try:
            job_key = key(job_id)
        except ValueError:
            # A malformed member would otherwise crash every dispatcher cycle.
            r.zrem(QUEUE, job_id)
            stats["orphans_pruned"] += 1
            logger.warning("pruned_malformed_queue_member member=%s", job_id)
            continue
        data = r.get(job_key)
        if data is None:
            # Queue entry survived the job record TTL — drop the reference.
            r.zrem(QUEUE, job_id)
            stats["orphans_pruned"] += 1
            continue
        job = json.loads(data)
        if job["status"] in TERMINAL:
            r.zrem(QUEUE, job_id)
            stats["terminal_pruned"] += 1
            continue
        if job["status"] == "processing" and job.get("next_at", 0) < now - LEASE - 300:
            # Lease expired long ago and dispatch has not repaired it: requeue.
            job.update(status="queued", next_at=now)
            r.set(job_key, json.dumps(job), ex=get_settings().job_ttl_seconds)
            r.zadd(QUEUE, {job_id: now})
            stats.setdefault("requeued", 0)
            stats["requeued"] += 1
            logger.warning("requeued_stale_job job_id=%s", job_id)
    stats["dlq_size"] = r.zcard(DLQ)
    metrics.set_gauge("jobs_queue_depth", float(r.zcard(QUEUE)))
    metrics.set_gauge("jobs_dlq_depth", float(stats["dlq_size"]))
    return stats
