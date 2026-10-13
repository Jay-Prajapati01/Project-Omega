"""Durable job queue tests (audit P0-6/P0-7/P0-9; plan API-010, ING-005).

Everything runs against fakeredis: no Redis server, no network. Ownership
comes from the `current_scope` ContextVar exactly as it does in production
(where CloudAuthMiddleware sets it), so cross-tenant isolation is exercised
the same way the API exercises it.
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.tenant import Scope, current_scope
from app.services import jobs

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
USER_A = "22222222-2222-2222-2222-222222222222"
USER_A2 = "44444444-4444-4444-4444-444444444444"
USER_B = "55555555-5555-5555-5555-555555555555"

RETRYABLE = {"error_code": "PROVIDER_TIMEOUT", "message": "timeout", "retryable": True}
FATAL = {"error_code": "BAD_INPUT", "message": "corrupt file", "retryable": False}


@pytest.fixture
def fake_redis():
    import fakeredis

    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch("app.services.jobs.client", new=lambda: fake):
        yield fake
    fake.flushall()


@pytest.fixture
def as_user_a():
    token = current_scope.set(Scope(TENANT_A, USER_A))
    yield
    current_scope.reset(token)


@pytest.fixture
def quota_5(as_user_a):
    """Daily job quota of 5 for the current tenant, restored afterwards."""
    from app.core import ratelimit

    ratelimit.reset_for_tests()
    settings = get_settings()
    previous = settings.max_jobs_per_tenant_per_day
    settings.max_jobs_per_tenant_per_day = 5
    yield settings
    settings.max_jobs_per_tenant_per_day = previous
    ratelimit.reset_for_tests()


def _create(**kwargs) -> dict:
    payload = kwargs.pop("payload", {"question": "what is mindmesh?"})
    return jobs.create(kwargs.pop("job_type", "chat"), payload,
                       kwargs.pop("resource_id", "res-1"), **kwargs)


# --- create / idempotency / quota -------------------------------------------


def test_create_enqueues_owned_job(fake_redis, as_user_a):
    job = _create()
    assert job["status"] == "queued"
    assert job["attempts"] == 0
    assert job["tenant_id"] == TENANT_A
    assert job["user_id"] == USER_A
    assert job["fingerprint"]
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is not None
    assert jobs.raw(job["job_id"])["payload"] == {"question": "what is mindmesh?"}


def test_public_view_hides_internal_fields(fake_redis, as_user_a):
    job = _create()
    view = jobs.public(job)
    assert set(view) == {"job_id", "resource_id", "job_type", "status",
                         "attempts", "result", "error"}
    assert "payload" not in view
    assert "tenant_id" not in view
    assert "fingerprint" not in view


def test_idempotent_create_returns_same_job(fake_redis, as_user_a):
    first = _create(idempotency_key="key-1")
    second = _create(idempotency_key="key-1")
    assert first["job_id"] == second["job_id"]
    assert fake_redis.zcard(jobs.QUEUE) == 1

    # Same key, different payload: a client error, never a second job.
    with pytest.raises(ValueError, match="Idempotency key already used"):
        _create(idempotency_key="key-1", payload={"question": "other"})


def test_create_without_key_is_unique(fake_redis, as_user_a):
    a, b = _create(), _create()
    assert a["job_id"] != b["job_id"]
    assert fake_redis.zcard(jobs.QUEUE) == 2


def test_key_requires_valid_uuid(fake_redis, as_user_a):
    assert jobs.key("c9a3f6e2-1111-2222-3333-444455556666").startswith("mindmesh:job:")
    with pytest.raises(ValueError):
        jobs.key("not-a-uuid")


def test_daily_quota_rejects_over_limit(fake_redis, quota_5):
    for i in range(5):
        _create(payload={"question": f"q{i}"})
    with pytest.raises(jobs.QuotaExceeded):
        _create(payload={"question": "one too many"})
    assert fake_redis.zcard(jobs.QUEUE) == 5


def test_quota_does_not_charge_idempotent_replays(fake_redis, quota_5):
    for i in range(5):
        _create(payload={"question": f"q{i}"})
    # A replay of an existing key must not consume quota nor create a job.
    replay = _create(payload={"question": "q0"}, idempotency_key="r-1")
    assert replay["job_id"]  # first use of this key: queued
    same = _create(payload={"question": "q0"}, idempotency_key="r-1")
    assert same["job_id"] == replay["job_id"]
    with pytest.raises(jobs.QuotaExceeded):
        _create(payload={"question": "sixth"}, idempotency_key="")  # quota full


# --- claim / finish ----------------------------------------------------------


def test_claim_sets_lease_and_finish_completes(fake_redis, as_user_a):
    job = _create()
    claimed, token = jobs.claim(job["job_id"])
    assert claimed["status"] == "processing"
    assert claimed["attempts"] == 1
    assert claimed["lease"] == token
    assert claimed["next_at"] > time.time()

    done = jobs.finish(job["job_id"], token, result={"answer": "42"})
    assert done["status"] == "completed"
    assert done["result"] == {"answer": "42"}
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is None
    assert fake_redis.zcard(jobs.DLQ) == 0


def test_double_claim_while_leased_is_denied(fake_redis, as_user_a):
    job = _create()
    jobs.claim(job["job_id"])
    with pytest.raises(PermissionError):
        jobs.claim(job["job_id"])


def test_claim_of_terminal_job_is_denied(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    jobs.finish(job["job_id"], token, result={})
    with pytest.raises(PermissionError):
        jobs.claim(job["job_id"])


def test_finish_with_stale_token_is_denied(fake_redis, as_user_a):
    job = _create()
    jobs.claim(job["job_id"])
    with pytest.raises(PermissionError, match="Stale worker lease"):
        jobs.finish(job["job_id"], "wrong-token", result={})
    assert jobs.raw(job["job_id"])["status"] == "processing"


def test_retryable_error_requeues_with_backoff(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    outcome = jobs.finish(job["job_id"], token, error=dict(RETRYABLE))
    assert outcome["status"] == "queued"
    assert outcome["error"] == RETRYABLE
    assert outcome["next_at"] > time.time()
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is not None
    assert fake_redis.zcard(jobs.DLQ) == 0


def test_fatal_error_dead_letters(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    outcome = jobs.finish(job["job_id"], token, error=dict(FATAL))
    assert outcome["status"] == "failed"
    assert fake_redis.zscore(jobs.DLQ, job["job_id"]) is not None
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is None


def test_retry_budget_exhausted_after_three_attempts(fake_redis, as_user_a):
    job = _create()
    for attempt in range(1, 4):
        _, token = jobs.claim(job["job_id"])
        outcome = jobs.finish(job["job_id"], token, error=dict(RETRYABLE))
        assert outcome["attempts"] == attempt
    # Third retryable failure is terminal: no fourth attempt is scheduled.
    assert outcome["status"] == "failed"
    assert outcome["error"] == RETRYABLE
    assert fake_redis.zscore(jobs.DLQ, job["job_id"]) is not None
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is None


def test_claim_on_exhausted_attempts_dead_letters(fake_redis, as_user_a):
    job = _create()
    # Drifted/forced state: queued with an already-spent retry budget.
    record = jobs.raw(job["job_id"])
    record["attempts"] = 3
    fake_redis.set(jobs.key(job["job_id"]), json.dumps(record))

    outcome, _token = jobs.claim(job["job_id"])
    assert outcome["status"] == "failed"
    assert outcome["error"]["error_code"] == "RETRY_EXHAUSTED"
    assert outcome["error"]["retryable"] is False
    assert fake_redis.zscore(jobs.DLQ, job["job_id"]) is not None


# --- cancel / ownership ------------------------------------------------------


def test_cancel_queued_job(fake_redis, as_user_a):
    job = _create()
    outcome = jobs.cancel(job["job_id"])
    assert outcome["status"] == "cancelled"
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is None
    # Terminal: cannot be claimed any more.
    with pytest.raises(PermissionError):
        jobs.claim(job["job_id"])


def test_cancel_processing_job_is_refused(fake_redis, as_user_a):
    job = _create()
    jobs.claim(job["job_id"])
    with pytest.raises(ValueError, match="Only queued jobs"):
        jobs.cancel(job["job_id"])
    assert jobs.raw(job["job_id"])["status"] == "processing"


def test_other_user_same_tenant_cannot_read_or_cancel(fake_redis, as_user_a):
    job = _create()
    token = current_scope.set(Scope(TENANT_A, USER_A2))
    try:
        with pytest.raises(KeyError):
            jobs.owned(job["job_id"])
        with pytest.raises(KeyError):
            jobs.cancel(job["job_id"])
    finally:
        current_scope.reset(token)
    assert jobs.raw(job["job_id"])["status"] == "queued"  # untouched


def test_other_tenant_cannot_read_or_cancel(fake_redis, as_user_a):
    job = _create()
    token = current_scope.set(Scope(TENANT_B, USER_B))
    try:
        with pytest.raises(KeyError):
            jobs.owned(job["job_id"])
        with pytest.raises(KeyError):
            jobs.cancel(job["job_id"])
    finally:
        current_scope.reset(token)
    assert jobs.raw(job["job_id"])["status"] == "queued"


def test_missing_scope_is_permission_error(fake_redis):
    current_scope.set(None)
    with pytest.raises(PermissionError, match="Authenticated ownership"):
        jobs.create("chat", {"question": "x"}, "res-1")


def test_unknown_job_raises_key_error(fake_redis, as_user_a):
    missing = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(KeyError):
        jobs.raw(missing)
    with pytest.raises(KeyError):
        jobs.owned(missing)


# --- DLQ replay --------------------------------------------------------------


def test_replay_moves_failed_job_back_to_queue(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    jobs.finish(job["job_id"], token, error=dict(FATAL))
    assert fake_redis.zcard(jobs.DLQ) == 1

    replayed = jobs.replay(job["job_id"])
    assert replayed["status"] == "queued"
    assert replayed["attempts"] == 0
    assert replayed["error"] is None
    assert fake_redis.zcard(jobs.DLQ) == 0
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is not None


def test_replay_rejects_non_failed_job(fake_redis, as_user_a):
    job = _create()
    with pytest.raises(ValueError, match="Only failed jobs"):
        jobs.replay(job["job_id"])


# --- reconcile ---------------------------------------------------------------


def test_reconcile_prunes_orphans_and_terminal_entries(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    jobs.finish(job["job_id"], token, result={"ok": True})

    # Drift: the queue holds a malformed member, a reference to a vanished
    # record, a terminal job that is still scheduled, and DLQ depth to report.
    fake_redis.zadd(jobs.QUEUE, {"ghost-job": time.time()})
    fake_redis.zadd(jobs.QUEUE, {"00000000-0000-4000-8000-000000000000": time.time()})
    fake_redis.zadd(jobs.QUEUE, {job["job_id"]: time.time()})

    stats = jobs.reconcile()
    assert stats["orphans_pruned"] == 2
    assert stats["terminal_pruned"] >= 1
    assert stats["dlq_size"] == 0
    assert fake_redis.zscore(jobs.QUEUE, "ghost-job") is None


def test_reconcile_requeues_long_expired_lease(fake_redis, as_user_a):
    job = _create()
    _, token = jobs.claim(job["job_id"])
    # Simulate a worker that died long ago (lease + grace period elapsed).
    record = jobs.raw(job["job_id"])
    record.update(next_at=time.time() - jobs.LEASE - 1000)
    fake_redis.set(jobs.key(job["job_id"]), json.dumps(record))

    stats = jobs.reconcile()
    assert stats.get("requeued") == 1
    assert jobs.raw(job["job_id"])["status"] == "queued"
    assert fake_redis.zscore(jobs.QUEUE, job["job_id"]) is not None
