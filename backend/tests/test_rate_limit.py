"""Rate limiting and quota tests (audit P0-11; plan API-007 rate-limit envelopes).

The autouse `_rate_limits_off` fixture in conftest disables limits for every
other test file; here they are switched back on explicitly. No Redis is
required (REDIS_URL is unset in the test environment) so every counter lives
in the in-process store, which `reset_for_tests()` clears around each test.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core import ratelimit
from app.core.config import get_settings
from app.core.tenant import Scope, current_scope

ORIGIN = "http://localhost:3000"  # matches CORS_ORIGINS in backend/.env


@pytest.fixture
def rl():
    """Enable rate limiting with tight limits; snapshot/restore all knobs."""
    settings = get_settings()
    snapshot = {
        name: getattr(settings, name)
        for name in (
            "rate_limit_enabled",
            "rate_limit_max_requests",
            "rate_limit_window",
            "rate_limit_read_per_min",
            "trust_proxy",
        )
    }
    settings.rate_limit_enabled = True
    settings.rate_limit_max_requests = 120
    settings.rate_limit_window = 60
    settings.rate_limit_read_per_min = 120
    ratelimit.reset_for_tests()
    yield settings
    for name, value in snapshot.items():
        setattr(settings, name, value)
    ratelimit.reset_for_tests()


def _app():
    from app.main import create_app

    return create_app()


# --- unit: sliding-window counter -------------------------------------------


def test_hit_allows_up_to_limit_then_blocks():
    ratelimit.reset_for_tests()
    assert ratelimit.hit("unit:1", 60, 2) == (True, 0)
    assert ratelimit.hit("unit:1", 60, 2) == (True, 0)
    allowed, retry = ratelimit.hit("unit:1", 60, 2)
    assert allowed is False
    assert retry >= 1


def test_hit_window_expiry_allows_again():
    ratelimit.reset_for_tests()
    # Backdate a hit beyond the window instead of sleeping.
    ratelimit._memory_store["unit:2"] = [time.time() - 120]
    allowed, _ = ratelimit.hit("unit:2", 60, 1)
    assert allowed is True


def test_hit_is_per_key_isolation():
    ratelimit.reset_for_tests()
    assert ratelimit.hit("unit:a", 60, 1) == (True, 0)
    assert ratelimit.hit("unit:a", 60, 1)[0] is False
    assert ratelimit.hit("unit:b", 60, 1) == (True, 0)


# --- unit: endpoint classes --------------------------------------------------


def test_endpoint_class_mapping():
    settings = get_settings()
    prefix = settings.api_prefix

    assert ratelimit.endpoint_class("GET", f"{prefix}/sources", prefix)[0] == "read"
    assert ratelimit.endpoint_class("POST", f"{prefix}/chat", prefix)[0] == "chat"
    assert ratelimit.endpoint_class("POST", f"{prefix}/chat/stream", prefix)[0] == "chat"
    assert ratelimit.endpoint_class("POST", f"{prefix}/search", prefix)[0] == "chat"
    assert ratelimit.endpoint_class("POST", f"{prefix}/compare", prefix)[0] == "chat"
    assert ratelimit.endpoint_class("POST", f"{prefix}/videos/process", prefix)[0] == "ingest"
    assert ratelimit.endpoint_class("POST", f"{prefix}/pdf/process", prefix)[0] == "ingest"
    assert ratelimit.endpoint_class("GET", f"{prefix}/jobs/some-id", prefix)[0] == "poll"
    assert ratelimit.endpoint_class("POST", f"{prefix}/notes", prefix)[0] == "write"
    assert ratelimit.endpoint_class("DELETE", f"{prefix}/notes/abc", prefix)[0] == "write"

    # Limits come from settings, windows are policy constants.
    assert ratelimit.endpoint_class("GET", f"{prefix}/sources", prefix)[1] == settings.rate_limit_read_per_min
    assert ratelimit.endpoint_class("GET", f"{prefix}/sources", prefix)[2] == 60
    assert ratelimit.endpoint_class("POST", f"{prefix}/videos/process", prefix)[2] == 3600


# --- unit: identity keying ---------------------------------------------------


def _bare_request(client_host: str = "1.2.3.4") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/sources",
            "headers": [],
            "client": (client_host, 1234),
        }
    )


def test_identity_key_uses_scope_when_present():
    token = current_scope.set(Scope("tenant-A", "user-1"))
    try:
        assert ratelimit._identity(_bare_request()) == "t:tenant-A:u:user-1"
    finally:
        current_scope.reset(token)


def test_identity_key_falls_back_to_client_ip():
    token = current_scope.set(None)
    try:
        assert ratelimit._identity(_bare_request("9.9.9.9")) == "ip:9.9.9.9"
    finally:
        current_scope.reset(token)


# --- middleware: 429 envelope ------------------------------------------------


def test_ip_limiter_429_envelope_and_cors(rl):
    settings = rl
    settings.rate_limit_max_requests = 3
    client = TestClient(_app())

    for _ in range(3):
        assert client.get("/api/sources", headers={"Origin": ORIGIN}).status_code == 200

    resp = client.get(
        "/api/sources",
        headers={"Origin": ORIGIN, "X-Request-ID": "req-abc-123"},
    )
    assert resp.status_code == 429
    body = resp.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert body["request_id"] == "req-abc-123"
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-Request-ID"] == "req-abc-123"
    # The limiter sits inside CORS: a browser must be able to read the 429.
    assert resp.headers["access-control-allow-origin"] == ORIGIN
    # Error body is a stable envelope, not a stack trace.
    assert set(body) == {"detail", "error_code", "request_id"}
    assert "Traceback" not in resp.text


def test_identity_limiter_blocks_reads_per_identity(rl):
    settings = rl
    settings.rate_limit_read_per_min = 2
    settings.rate_limit_max_requests = 1000  # IP layer must not trip first
    client = TestClient(_app())

    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/notes").status_code == 200
    resp = client.get("/api/stats")
    assert resp.status_code == 429
    assert "read" in resp.json()["detail"]
    assert resp.json()["error_code"] == "RATE_LIMITED"
    # With trust_proxy off, a spoofed XFF shares the same identity bucket.
    resp = client.get("/api/stats", headers={"X-Forwarded-For": "8.8.4.4"})
    assert resp.status_code == 429


def test_health_endpoints_are_exempt(rl):
    settings = rl
    settings.rate_limit_max_requests = 2
    client = TestClient(_app())

    # /api/health/detailed is covered by the same prefix exemption in
    # test_auth_matrix (it needs mocked dependencies); keep this loop on the
    # cheap probes so no real network call happens here.
    for _ in range(5):
        assert client.get("/api/health").status_code == 200
        assert client.get("/health").status_code == 200

    # Limits are demonstrably active for everything else...
    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/sources").status_code == 429


def test_xff_is_ignored_when_trust_proxy_disabled(rl):
    settings = rl
    settings.rate_limit_max_requests = 2
    settings.trust_proxy = False
    client = TestClient(_app())

    assert client.get("/api/sources").status_code == 200
    assert client.get("/api/sources", headers={"X-Forwarded-For": "10.1.2.3"}).status_code == 200
    # Same bucket despite a fresh spoofed XFF: the header is not trusted.
    assert (
        client.get("/api/sources", headers={"X-Forwarded-For": "10.9.9.9"}).status_code
        == 429
    )


def test_xff_is_honoured_when_trust_proxy_enabled(rl):
    settings = rl
    settings.rate_limit_max_requests = 2
    settings.trust_proxy = True
    client = TestClient(_app())

    assert client.get("/api/sources", headers={"X-Forwarded-For": "11.1.1.1"}).status_code == 200
    assert client.get("/api/sources", headers={"X-Forwarded-For": "11.2.2.2"}).status_code == 200
    assert client.get("/api/sources", headers={"X-Forwarded-For": "11.3.3.3"}).status_code == 200


def test_disabled_limits_allow_unlimited_requests(rl):
    settings = rl
    settings.rate_limit_enabled = False
    settings.rate_limit_max_requests = 1
    client = TestClient(_app())
    for _ in range(5):
        assert client.get("/api/sources").status_code == 200


# --- unit: daily quotas ------------------------------------------------------


def test_quota_hit_accumulates_and_blocks_over_limit():
    ratelimit.reset_for_tests()
    assert ratelimit.quota_hit("tenant-1", "jobs", 1, 2) == (True, 1)
    assert ratelimit.quota_hit("tenant-1", "jobs", 1, 2) == (True, 2)
    allowed, used = ratelimit.quota_hit("tenant-1", "jobs", 1, 2)
    assert allowed is False and used == 3
    # Quotas are per tenant: another tenant is unaffected.
    assert ratelimit.quota_hit("tenant-2", "jobs", 1, 2) == (True, 1)
    # A non-positive limit disables the quota entirely.
    assert ratelimit.quota_hit("tenant-3", "jobs", 1, 0) == (True, 0)


def test_quota_hit_is_per_kind():
    ratelimit.reset_for_tests()
    assert ratelimit.quota_hit("tenant-1", "jobs", 1, 1) == (True, 1)
    assert ratelimit.quota_hit("tenant-1", "jobs", 1, 1)[0] is False
    # A different kind keeps its own counter.
    assert ratelimit.quota_hit("tenant-1", "bytes", 1, 1) == (True, 1)
