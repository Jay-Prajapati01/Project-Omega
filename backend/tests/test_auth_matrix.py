"""Authorization matrix tests (audit P0-3/P0-4/P0-15; plan SEC-001..009, API-009/010).

Modal (cloud) mode is exercised by building a second app instance with
`create_app()` after flipping the execution mode. The Supabase token
endpoint, the membership resolver, cloud state reads and Qdrant are all
mocked: no network, no database. The tests prove that

* every non-health route demands a valid bearer token,
* identity comes only from the validated token + membership table,
* forged identity headers are ignored,
* local X-API-Key can never bypass (or replace) cloud membership,
* legacy synchronous ingestion routes are not mounted in cloud mode,
* the job facade enforces owner scoping end-to-end.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.tenant import Scope, current_scope

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
USER_ID = "22222222-2222-2222-2222-222222222222"

PROTECTED_ROUTES = [
    ("GET", "/api/sources"),
    ("GET", "/api/notes"),
    ("GET", "/api/graph"),
    ("GET", "/api/timeline"),
    ("GET", "/api/stats"),
    ("GET", "/api/chat/conversations/whatever"),
    ("POST", "/api/chat"),
    ("POST", "/api/search"),
    ("POST", "/api/compare"),
    ("POST", "/api/videos/process"),
    ("GET", "/api/jobs/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/jobs/00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/metrics"),
    ("GET", "/"),
]


# conftest provides `auth_state` / `modal_app` / `modal_client`; this suite
# simply names the modal client `client` for brevity.
@pytest.fixture
def client(modal_client):
    return modal_client


# --- SEC-001: bearer is mandatory on every non-health route -----------------


def test_missing_token_denied_on_every_protected_route(client):
    for method, path in PROTECTED_ROUTES:
        resp = client.request(method, path, json={} if method == "POST" else None)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
        assert resp.json().get("error_code") == "AUTH_REQUIRED"
        # Denied responses must not leak any resource payload.
        assert "items" not in resp.json()
        assert "sources" not in resp.json()


def test_health_endpoints_are_public_in_cloud_mode(client):
    import fakeredis

    fake = fakeredis.FakeStrictRedis(decode_responses=True)

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *_args, **_kwargs):
            return None

    # Hermetic: fake Redis/Postgres/Qdrant so the probe never touches network.
    with (
        patch("app.services.jobs.client", new=lambda: fake),
        patch("app.services.cloud_db.connect", new=_FakeConn),
        patch(
            "app.services.vectorstore.get_client",
            new=lambda: SimpleNamespace(get_collections=lambda: []),
        ),
    ):
        for path in ("/api/health", "/health", "/api/health/detailed"):
            resp = client.get(path)
            assert resp.status_code == 200, path
        detail = client.get("/api/health/detailed").json()
        assert detail["status"] == "ok"
        assert set(detail["checks"]) >= {"app", "redis", "database", "qdrant"}
        # Readiness must degrade gracefully, never 500, and never leak URLs.
        body = client.get("/api/health/detailed").text
    assert "supabase" not in body.lower()
    assert "password" not in body.lower()
    assert "rediss://" not in body


def test_malformed_and_oversized_tokens_denied(client):
    resp = client.get("/api/sources", headers={"Authorization": "Basic dXNlcjpwdw=="})
    assert resp.status_code == 401
    resp = client.get("/api/sources", headers={"Authorization": "Bearer " + "x" * 9000})
    assert resp.status_code == 401


def test_invalid_token_denied(auth_state, client):
    auth_state.token_status = 401
    resp = client.get("/api/sources", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTH_INVALID"


# --- SEC-003: membership is mandatory; no default tenant is inferred --------


def test_valid_token_without_membership_forbidden(auth_state, client):
    auth_state.resolve_error = PermissionError("no active membership")
    resp = client.get("/api/sources", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NO_MEMBERSHIP"


def test_auth_backend_outage_is_503_not_500(auth_state, client):
    auth_state.network_error = ConnectionError("supabase down")
    resp = client.get("/api/sources", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 503
    assert resp.json()["error_code"] == "AUTH_UNAVAILABLE"


# --- SEC-004: identity comes from the server, never from request headers ----


def test_forged_identity_headers_are_ignored(auth_state):
    from app.core.cloud_auth import CloudAuthMiddleware

    recorded: dict = {}

    async def inner(scope, receive, send):
        recorded["scope"] = current_scope.get()
        await JSONResponse({"ok": True})(scope, receive, send)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/sources",
        "raw_path": b"/api/sources",
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
        "client": ("127.0.0.1", 1234),
        "headers": [
            (b"authorization", b"Bearer good"),
            (b"x-tenant-id", TENANT_B.encode()),
            (b"x-user-id", b"attacker"),
            (b"x-supabase-tenant", TENANT_B.encode()),
        ],
    }
    with (
        patch("httpx.AsyncClient.get", new=auth_state.httpx_get()),
        patch("app.core.cloud_auth.resolve_user", new=auth_state.resolver()),
    ):
        asyncio.run(CloudAuthMiddleware(inner)(scope, receive, send))
    assert sent and sent[0]["status"] == 200
    resolved = recorded["scope"]
    assert resolved == auth_state.scope
    assert resolved.tenant_id == TENANT_A  # forged X-Tenant-ID ignored
    assert resolved.user_id == USER_ID  # forged X-User-ID ignored


def test_valid_token_reaches_tenant_scoped_reads(client):
    resp = client.get("/api/sources", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# --- SEC-009: local API key vs cloud membership -----------------------------


def test_local_api_key_cannot_bypass_cloud_auth(auth_state, client):
    settings = get_settings()
    settings.api_key = "sekret-local-key"
    try:
        # Correct local key but no bearer: still denied by cloud auth.
        resp = client.post(
            "/api/notes",
            json={"title": "x", "body": "y"},
            headers={"X-API-Key": "sekret-local-key"},
        )
        assert resp.status_code == 401
        # Bearer alone is sufficient: cloud identity wins, local key unused
        # (and a wrong local key never overrides a valid bearer).
        with patch(
            "app.services.store.add_note",
            new=lambda title, body: {"id": "n1", "title": title, "body": body},
        ):
            resp = client.post(
                "/api/notes",
                json={"title": "allowed", "body": "y"},
                headers={"Authorization": "Bearer good"},
            )
            assert resp.status_code == 200
            resp = client.post(
                "/api/notes",
                json={"title": "allowed", "body": "y"},
                headers={"Authorization": "Bearer good", "X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 200
    finally:
        settings.api_key = ""


# --- P0-15: legacy sync routes are not mounted in cloud mode ----------------


def test_legacy_sync_routes_not_mounted_in_modal(modal_app):
    names = {r.name for r in modal_app.routes if hasattr(r, "name")}
    legacy = {"chat", "search", "process_video", "process_instagram"}
    assert not (names & legacy), f"legacy handlers mounted: {names & legacy}"
    facade = {"queue_chat", "queue_search", "queue_videos", "queue_instagram",
              "stream_chat", "stream_videos", "stream_instagram", "status", "cancel"}
    assert facade <= names, f"missing facade routes: {facade - names}"
    # Chat history GET survives (facade has no equivalent).
    assert any(
        getattr(r, "path", "") == "/api/chat/conversations/{conversation_id}"
        for r in modal_app.routes
    )


# --- API-009/010 + SEC-007: job facade ownership end-to-end -----------------


@pytest.fixture
def modal_jobs_client(modal_app, auth_state):
    import fakeredis


    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch("app.services.jobs.client", new=lambda: fake):
        yield TestClient(modal_app), fake
    fake.flushall()


def test_job_facade_lifecycle_and_owner_scoping(modal_jobs_client, auth_state):
    client, fake = modal_jobs_client

    # Enqueue a chat job through the facade.
    resp = client.post(
        "/api/chat",
        json={"question": "What is MindMesh?"},
        headers={"Authorization": "Bearer good"},
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "queued"
    assert job["job_id"]
    assert "payload" not in job and "tenant_id" not in job  # public view only
    assert resp.headers["Location"].endswith(job["job_id"])

    # Owner can read status and cancel while queued.
    resp = client.get(f"/api/jobs/{job['job_id']}", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    # Same tenant, different user: no access (scope includes user).
    auth_state.scope = Scope(TENANT_A, "99999999-9999-9999-9999-999999999999")
    resp = client.get(f"/api/jobs/{job['job_id']}", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 404  # existence must not leak

    # Other tenant: no access either.
    auth_state.scope = Scope(TENANT_B, USER_ID)
    resp = client.get(f"/api/jobs/{job['job_id']}", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 404
    resp = client.delete(f"/api/jobs/{job['job_id']}", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 404

    # Back to the owner: cancel succeeds.
    auth_state.scope = Scope(TENANT_A, USER_ID)
    resp = client.delete(f"/api/jobs/{job['job_id']}", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_job_facade_idempotency_and_validation(modal_jobs_client):
    client, fake = modal_jobs_client
    headers = {"Authorization": "Bearer good", "Idempotency-Key": "abc-123"}

    first = client.post("/api/chat", json={"question": "same question"}, headers=headers)
    assert first.status_code == 202
    second = client.post("/api/chat", json={"question": "same question"}, headers=headers)
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert fake.zcard("mindmesh:jobs:due") == 1

    # The same idempotency key with a different payload is a client error.
    conflict = client.post(
        "/api/chat",
        json={"question": "different question"},
        headers=headers,
    )
    assert conflict.status_code == 400

    # Schema violations are rejected before anything is queued.
    resp = client.post("/api/chat", json={}, headers={"Authorization": "Bearer good"})
    assert resp.status_code == 422
    resp = client.post("/api/videos/process", json={}, headers={"Authorization": "Bearer good"})
    assert resp.status_code == 422
    resp = client.post(
        "/api/chat",
        json={"question": "x"},
        headers={"Authorization": "Bearer good", "Idempotency-Key": "k" * 200},
    )
    assert resp.status_code == 400


def test_excluded_file_upload_routes_are_not_mounted(modal_jobs_client, auth_state):
    client, fake = modal_jobs_client
    auth = {"Authorization": "Bearer good"}

    # File ingestion is outside this clone's selected feature set.
    resp = client.post(
        "/api/pdf/process",
        files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=auth,
    )
    assert resp.status_code == 404

    resp = client.post(
        "/api/pdf/process",
        files={"file": ("fake.pdf", b"this is not a pdf at all", "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 404

    # Nothing was staged and nothing was queued.
    assert fake.zcard("mindmesh:jobs:due") == 0
