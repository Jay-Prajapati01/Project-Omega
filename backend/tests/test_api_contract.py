"""API contract tests (test plan API-001..012).

Local (non-modal) mode unless the test explicitly uses the `modal_*` fixtures
from conftest. Everything is hermetic: the LLM, embeddings and vector search
are faked, store/graph state is redirected to a temp directory, and the job
queue runs on fakeredis.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models.schemas import SourceItem
from app.services import store

ORIGIN = "http://localhost:3000"


@pytest.fixture
def client(hermetic):
    return TestClient(app)


@pytest.fixture
def isolated_store(tmp_path):
    """Redirect the JSON store / file storage / graph to a temp directory."""
    settings = get_settings()
    previous = settings.data_dir
    settings.data_dir = str(tmp_path)
    store.invalidate_cache()
    yield settings
    settings.data_dir = previous
    store.invalidate_cache()


def _seed(
    source_id: str,
    source_type: str = "pdf",
    title: str | None = None,
    created_at: datetime | None = None,
    **kwargs,
) -> SourceItem:
    item = SourceItem(
        source_id=source_id,
        source_type=source_type,
        title=title or source_id,
        created_at=created_at or datetime.now(timezone.utc),
        **kwargs,
    )
    store.add_source(item)
    return item


# --- API-001: liveness vs dependency health ----------------------------------


def test_liveness_endpoints_are_public_and_light(client):
    for path in ("/api/health", "/health"):
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert {"app", "environment", "version"} <= set(body)
        # Liveness never reports on dependencies.
        assert "checks" not in body


def test_detailed_health_degrades_without_dependencies(client):
    with (
        patch("httpx.AsyncClient.get", side_effect=ConnectionError("no ollama")),
        patch(
            "app.services.vectorstore.get_client",
            side_effect=ConnectionError("no qdrant"),
        ),
    ):
        resp = client.get("/api/health/detailed")
    assert resp.status_code == 200  # degraded, never 500
    body = resp.json()
    assert body["status"] == "degraded"
    assert {"ollama", "qdrant"} <= set(body["checks"])
    # Public route never leaks credentials or connection strings.
    text = resp.text.lower()
    assert "password" not in text
    assert "supabase" not in text
    assert "rediss://" not in resp.text


# --- API-002: source listing, filters, pagination ----------------------------


def test_sources_filter_and_pagination(isolated_store, client):
    for i in range(3):
        _seed(f"pdf-{i}", "pdf")
    for i in range(2):
        _seed(f"vid-{i}", "video")

    page1 = client.get("/api/sources?page=1&page_size=2").json()
    assert page1["total"] == 5
    assert page1["total_pages"] == 3
    assert len(page1["items"]) == 2
    page2 = client.get("/api/sources?page=2&page_size=2").json()
    assert len(page2["items"]) == 2
    ids1 = {s["source_id"] for s in page1["items"]}
    ids2 = {s["source_id"] for s in page2["items"]}
    assert not ids1 & ids2  # pages never overlap

    filtered = client.get("/api/sources?source_type=video").json()
    assert filtered["total"] == 2
    assert all(s["source_type"] == "video" for s in filtered["items"])

    empty = client.get("/api/sources?source_type=nonexistent").json()
    assert empty == {"items": [], "total": 0, "page": 1,
                     "page_size": 20, "total_pages": 0}


def test_source_metadata_is_complete(isolated_store, client):
    _seed("meta-1", "pdf", title="Report", url="https://example.com/r")
    item = client.get("/api/sources/meta-1").json()
    assert item["source_id"] == "meta-1"
    assert item["source_type"] == "pdf"
    assert item["title"] == "Report"
    assert "created_at" in item and "chunks_indexed" in item


def test_unknown_source_is_404(client):
    assert client.get("/api/sources/does-not-exist").status_code == 404


# --- API-003: download / view / link -----------------------------------------


def test_download_serves_file_with_disposition(isolated_store, client):
    import app.services.file_storage as file_storage

    target = Path(isolated_store.data_dir) / "files" / "pdf" / "dl-1.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4 content")
    _seed("dl-1", file_path="files/pdf/dl-1.pdf", file_name="report.pdf",
          mime_type="application/pdf")

    resp = client.get("/api/sources/dl-1/download")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 content"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "attachment" in resp.headers["content-disposition"]
    assert "report.pdf" in resp.headers["content-disposition"]
    assert file_storage.get_file_path("files/pdf/dl-1.pdf") is not None


def test_view_serves_file_inline(isolated_store, client):
    target = Path(isolated_store.data_dir) / "files" / "pdf" / "view-1.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4 inline")
    _seed("view-1", file_path="files/pdf/view-1.pdf")

    resp = client.get("/api/sources/view-1/view")
    assert resp.status_code == 200
    assert "inline" in resp.headers["content-disposition"]


def test_download_variants_are_404_without_leaking_paths(isolated_store, client):
    # Unknown source.
    assert client.get("/api/sources/nope/download").status_code == 404
    # Known source, no file ever stored.
    _seed("nofile-1")
    resp = client.get("/api/sources/nofile-1/download")
    assert resp.status_code == 404
    assert "No original file" in resp.json()["detail"]
    # File registered but missing on disk.
    _seed("ghost-1", file_path="files/pdf/ghost-1.pdf")
    resp = client.get("/api/sources/ghost-1/download")
    assert resp.status_code == 404
    assert "not found on disk" in resp.json()["detail"]
    # Path traversal in file_path is refused by the storage layer.
    _seed("evil-1", file_path="../../outside-secret.txt")
    resp = client.get("/api/sources/evil-1/download")
    assert resp.status_code == 404
    assert "outside-secret" not in resp.text


def test_link_is_cloud_only(isolated_store, client):
    _seed("link-1")
    resp = client.get("/api/sources/link-1/link")
    assert resp.status_code == 404
    assert "local mode" in resp.json()["detail"]


# --- API-004: source deletion ------------------------------------------------


def test_delete_source_removes_store_entry_and_file(isolated_store, client):
    target = Path(isolated_store.data_dir) / "files" / "pdf" / "del-1.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4 bye")
    _seed("del-1", file_path="files/pdf/del-1.pdf")

    with patch("app.services.vectorstore.delete_by_source_id"):
        resp = client.delete("/api/sources/del-1")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "del-1"
    assert client.get("/api/sources/del-1").status_code == 404
    assert not target.exists()

    # Repeated delete is a clean 404, not a 500.
    assert client.delete("/api/sources/del-1").status_code == 404


def test_delete_tolerates_downstream_failure_in_local_mode(isolated_store, client):
    _seed("del-2")
    with (
        patch(
            "app.services.vectorstore.delete_by_source_id",
            side_effect=ConnectionError("qdrant down"),
        ),
        patch("app.services.graph.remove_source", side_effect=OSError("graph gone")),
    ):
        resp = client.delete("/api/sources/del-2")
    # Local mode is best-effort: it logs and still removes the metadata.
    assert resp.status_code == 200
    assert client.get("/api/sources/del-2").status_code == 404


# --- API-005: notes ----------------------------------------------------------


def test_note_validation(isolated_store, client):
    assert client.post("/api/notes", json={}).status_code == 422
    assert client.post("/api/notes", json={"title": ""}).status_code == 422
    assert client.post("/api/notes", json={"body": "no title"}).status_code == 422
    ok = client.post("/api/notes", json={"title": "title only"})
    assert ok.status_code == 200
    client.delete(f"/api/notes/{ok.json()['id']}")


def test_note_lifecycle_and_repeated_delete(isolated_store, client):
    created = client.post(
        "/api/notes", json={"title": "Ünïcode title", "body": "body text"}
    ).json()
    assert created["title"] == "Ünïcode title"
    assert created["id"]

    listed = client.get("/api/notes").json()
    assert any(n["id"] == created["id"] for n in listed)

    assert client.delete(f"/api/notes/{created['id']}").status_code == 200
    assert all(n["id"] != created["id"] for n in client.get("/api/notes").json())
    assert client.delete(f"/api/notes/{created['id']}").status_code == 404


# --- API-006: stats / timeline / graph ---------------------------------------


def test_stats_shape_agrees_with_store(isolated_store, client):
    _seed("s-pdf-1", "pdf")
    _seed("s-pdf-2", "pdf")
    _seed("s-vid-1", "video")

    stats = client.get("/api/stats").json()
    assert stats["total_sources"] == 3
    assert stats["sources_by_type"] == {"pdf": 2, "video": 1}
    assert stats["indexed_chunks"] >= 0
    assert {"total_files_stored", "total_storage_bytes", "recent_sources",
            "recent_searches", "recent_questions", "knowledge_growth"} <= set(stats)
    listed = client.get("/api/sources").json()
    assert stats["total_sources"] == listed["total"]  # counts agree with listing


def test_timeline_buckets_and_order(isolated_store, client):
    _seed("t-new", created_at=datetime.now(timezone.utc))
    _seed("t-old", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    _seed("t-today")  # default created_at: now -> Today

    groups = client.get("/api/timeline").json()["groups"]
    labels = [g["label"] for g in groups]
    canonical = ["Today", "Yesterday", "This week", "This month", "Earlier"]
    assert labels == sorted(labels, key=canonical.index)
    by_label = {g["label"]: g["items"] for g in groups}
    assert "Today" in by_label
    assert "Earlier" in by_label
    ids = {i["source_id"] for g in groups for i in g["items"]}
    assert {"t-new", "t-old"} <= ids
    assert {"source_id", "source_type", "title", "created_at"} <= set(
        by_label["Today"][0]
    )


def test_graph_shape_empty_by_default(isolated_store, client):
    body = client.get("/api/graph").json()
    assert set(body) == {"nodes", "edges"}
    assert body["nodes"] == []
    assert body["edges"] == []


# --- API-007: chat / search / streaming --------------------------------------


def test_chat_response_schema(client, hermetic):
    resp = client.post("/api/chat", json={"question": "test query"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"question", "conversation_id", "answer", "citations",
                         "related_sources", "search_time_ms", "chunks_searched", "sources_searched"}
    assert body["citations"], "retrieval produced hits, citations must follow"
    assert {"source_id", "source_type", "snippet"} <= set(body["citations"][0])


def test_conversation_history_round_trip(client, hermetic, isolated_store):
    first = client.post(
        "/api/chat", json={"question": "What is AI?", "conversation_id": "conv-42"}
    )
    assert first.status_code == 200
    assert first.json()["conversation_id"] == "conv-42"

    history = client.get("/api/chat/conversations/conv-42")
    assert history.status_code == 200
    assert history.json()["turns"]

    assert client.get("/api/chat/conversations/no-such").status_code == 404


def test_chat_stream_framing(client, hermetic, isolated_store):
    with client.stream("POST", "/api/chat/stream",
                       json={"question": "what is ai"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        lines = [ln for ln in "".join(resp.iter_text()).splitlines() if ln.strip()]
    assert lines, "stream must emit events"
    assert all(ln.startswith("data: ") for ln in lines)
    assert any('"type": "done"' in ln for ln in lines)


def test_chat_failure_is_redacted(hermetic, isolated_store):
    broken = TestClient(app, raise_server_exceptions=False)
    with patch(
        "app.services.rag.answer", side_effect=RuntimeError("secret db://user:pw@host")
    ):
        resp = broken.post("/api/chat", json={"question": "anything"})
    assert resp.status_code == 500
    assert "secret" not in resp.text
    assert "user:pw" not in resp.text
    assert "Traceback" not in resp.text


# --- API-008: compare --------------------------------------------------------


def test_compare_rejects_same_or_missing_ids(client):
    resp = client.post(
        "/api/compare", json={"source_id_a": "same", "source_id_b": "same"}
    )
    assert resp.status_code == 400
    assert "different sources" in resp.json()["detail"]
    assert client.post("/api/compare", json={}).status_code == 422
    assert client.post("/api/compare", json={"source_id_a": "only-a"}).status_code == 422


def test_compare_result_schema(client, hermetic, isolated_store):
    with patch(
        "app.services.vectorstore.get_chunks_by_source",
        side_effect=lambda sid, *a, **k: [{"text": f"content of {sid}"}],
    ):
        resp = client.post(
            "/api/compare", json={"source_id_a": "a-1", "source_id_b": "b-1"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"analysis", "source_a", "source_b"}
    assert body["source_a"] == "a-1" and body["source_b"] == "b-1"
    assert body["analysis"]


def test_compare_without_content_is_graceful(client, hermetic, isolated_store):
    with patch("app.services.vectorstore.get_chunks_by_source", return_value=[]):
        resp = client.post(
            "/api/compare", json={"source_id_a": "empty", "source_id_b": "void"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "no indexed content" in body["analysis"]
    assert body["source_a"] == "empty"


# --- API-009: ingestion payload validation (local mode) ----------------------


def test_process_endpoints_validate_before_doing_work(client):
    for path in ("/api/videos/process", "/api/web/process"):
        assert client.post(path, json={}).status_code == 422, path
        assert client.post(path, json={"url": ""}).status_code == 422, path
        assert client.get(path).status_code == 405, path  # POST-only


# --- API-010: job status/cancel contract (modal mode) ------------------------


@pytest.fixture
def modal_jobs(modal_app, auth_state):
    import fakeredis


    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch("app.services.jobs.client", new=lambda: fake):
        yield TestClient(modal_app), fake
    fake.flushall()


def _enqueue(client, question="contract question") -> dict:
    resp = client.post(
        "/api/chat",
        json={"question": question},
        headers={"Authorization": "Bearer good"},
    )
    assert resp.status_code == 202
    return resp.json()


def test_job_status_exposes_terminal_result_and_retry_fields(modal_jobs, auth_state):
    from app.services import jobs

    client, fake = modal_jobs
    auth = {"Authorization": "Bearer good"}
    job = _enqueue(client)

    # Terminal success: status reflects the stored result, public view only.
    claimed, token = jobs.claim(job["job_id"])
    jobs.finish(job["job_id"], token, result={"answer": "42"})
    resp = client.get(f"/api/jobs/{job['job_id']}", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["attempts"] == 1
    assert body["result"] == {"answer": "42"}
    assert body["error"] is None
    assert "payload" not in body and "tenant_id" not in body

    # Terminal failure carries a structured, retry-aware error envelope.
    failed = _enqueue(client, "second question")
    _, token = jobs.claim(failed["job_id"])
    jobs.finish(
        failed["job_id"],
        token,
        error={"error_code": "BAD_INPUT", "message": "corrupt", "retryable": False},
    )
    body = client.get(f"/api/jobs/{failed['job_id']}", headers=auth).json()
    assert body["status"] == "failed"
    assert body["error"]["error_code"] == "BAD_INPUT"
    assert body["error"]["retryable"] is False
    assert body["attempts"] == 1


def test_job_unknown_id_is_404_and_cancel_transitions(modal_jobs, auth_state):
    client, fake = modal_jobs
    auth = {"Authorization": "Bearer good"}
    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/jobs/{unknown}", headers=auth).status_code == 404
    assert client.delete(f"/api/jobs/{unknown}", headers=auth).status_code == 404

    job = _enqueue(client, "cancel me")
    resp = client.delete(f"/api/jobs/{job['job_id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    # Terminal: cancelling again is a conflict, not a silent success.
    assert client.delete(f"/api/jobs/{job['job_id']}", headers=auth).status_code == 409


def test_cancel_processing_job_is_409(modal_jobs, auth_state):
    from app.services import jobs

    client, fake = modal_jobs
    auth = {"Authorization": "Bearer good"}
    job = _enqueue(client, "processing job")
    jobs.claim(job["job_id"])
    resp = client.delete(f"/api/jobs/{job['job_id']}", headers=auth)
    assert resp.status_code == 409
    assert "queued" in resp.json()["detail"]


# --- API-011: CORS, headers, error envelopes ---------------------------------


def test_cors_preflight_allows_only_configured_origin(client):
    settings = get_settings()
    allowed = settings.cors_origin_list[0]
    resp = client.options(
        "/api/sources",
        headers={
            "Origin": allowed,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers["access-control-allow-origin"] == allowed
    assert resp.headers["access-control-allow-credentials"] == "true"
    assert "POST" in resp.headers["access-control-allow-methods"]
    # Never a wildcard origin alongside credentials.
    assert resp.headers["access-control-allow-origin"] != "*"


def test_cors_omits_headers_for_unlisted_origin(client):
    resp = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_security_headers_and_request_id(client):
    resp = client.get("/api/sources", headers={"X-Request-ID": "trace-me-1"})
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in resp.headers["permissions-policy"]
    assert resp.headers["x-request-id"] == "trace-me-1"
    assert resp.headers["cache-control"] == "no-store"
    # HSTS is a production-only header (dev must not pin the origin).
    assert "strict-transport-security" not in resp.headers


def test_error_envelope_is_consistent(client):
    resp = client.get("/api/sources/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body) == {"detail"}
    assert "Traceback" not in resp.text
    assert "FileNotFound" not in resp.text


# --- API-012: OpenAPI / debug surface ----------------------------------------


def test_openapi_documents_shipped_endpoints(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"]
    assert spec["info"]["version"]
    expected = {
        "/api/health",
        "/api/health/detailed",
        "/api/sources",
        "/api/sources/{source_id}",
        "/api/sources/{source_id}/download",
        "/api/sources/{source_id}/view",
        "/api/notes",
        "/api/chat",
        "/api/chat/stream",
        "/api/chat/conversations/{conversation_id}",
        "/api/search",
        "/api/compare",
        "/api/graph",
        "/api/timeline",
        "/api/stats",
        "/",
    }
    missing = expected - set(spec["paths"])
    assert not missing, f"undocumented endpoints: {missing}"
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in methods:
                continue  # path-level "parameters" etc.
            assert "responses" in op, f"{method.upper()} {path} has no responses"


def test_docs_ui_available_outside_production(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_no_debug_or_shell_endpoints_in_api(client):
    spec = client.get("/openapi.json").json()
    forbidden = ("eval", "exec", "shell", "console", "__debug__", "/debug")
    offenders = [p for p in spec["paths"] if any(f in p.lower() for f in forbidden)]
    assert not offenders, f"dangerous endpoints exposed: {offenders}"


def test_metrics_is_text_and_leak_free(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in resp.text
    assert "password" not in resp.text.lower()
    assert "supabase" not in resp.text.lower()
