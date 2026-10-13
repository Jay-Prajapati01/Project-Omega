"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client(hermetic):
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "MindMesh"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "MindMesh" in data["app"]


def test_stats(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "indexed_chunks" in data
    assert "total_sources" in data
    assert "sources_by_type" in data


def test_list_sources(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data


def test_list_sources_pagination(client):
    resp = client.get("/api/sources?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


def test_chat_empty_question(client):
    resp = client.post("/api/chat", json={"question": ""})
    assert resp.status_code == 200  # Backend handles empty gracefully
    data = resp.json()
    # Graceful means no retrieval ran: no fabricated citations.
    assert data["citations"] == []
    assert data["chunks_searched"] == 0


def test_chat_whitespace_question_is_graceful(client):
    resp = client.post("/api/chat", json={"question": "   "})
    assert resp.status_code == 200
    data = resp.json()
    assert data["citations"] == []
    assert data["chunks_searched"] == 0


def test_chat_stream_blank_question_is_graceful(client):
    with client.stream("POST", "/api/chat/stream", json={"question": ""}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert '"type": "done"' in body
    assert "Please enter a question" in body


def test_chat_oversized_question_rejected(client):
    resp = client.post("/api/chat", json={"question": "x" * 5000})
    assert resp.status_code == 422


def test_search_blank_query_is_graceful(client):
    for query in ("", "   "):
        resp = client.post("/api/search", json={"query": query})
        assert resp.status_code == 200
        data = resp.json()
        # Hermetic fixture would return hits for any non-blank query.
        assert data["hits"] == []
        assert data["chunks_searched"] == 0


def test_search_oversized_query_rejected(client):
    resp = client.post("/api/search", json={"query": "x" * 2000})
    assert resp.status_code == 422


def test_chat_with_history(client):
    resp = client.post("/api/chat", json={
        "question": "What is AI?",
        "history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data


def test_search(client):
    resp = client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200
    data = resp.json()
    assert "hits" in data
    assert "query" in data


def test_get_source_not_found(client):
    resp = client.get("/api/sources/nonexistent")
    assert resp.status_code == 404


def test_delete_source_not_found(client):
    resp = client.delete("/api/sources/nonexistent")
    assert resp.status_code == 404


def test_notes_crud(client):
    # Create
    resp = client.post("/api/notes", json={"title": "Test", "body": "Body"})
    assert resp.status_code == 200
    note = resp.json()
    assert note["title"] == "Test"
    
    # List
    resp = client.get("/api/notes")
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) >= 1
    
    # Delete
    resp = client.delete(f"/api/notes/{note['id']}")
    assert resp.status_code == 200


def test_search_matches_workspace_notes(client):
    created = client.post(
        "/api/notes",
        json={"title": "Zorblax Project", "body": "Maintenance notes for zorblax flanges."},
    ).json()
    try:
        resp = client.post("/api/search", json={"query": "zorblax"})
        assert resp.status_code == 200
        note_hits = [h for h in resp.json()["hits"] if h["source_type"] == "note"]
        assert note_hits, "notes should be discoverable through search"
        assert note_hits[0]["source_id"] == created["id"]
        assert note_hits[0]["score"] >= 0.8
    finally:
        client.delete(f"/api/notes/{created['id']}")


def test_search_note_hits_respect_source_type_filter(client):
    created = client.post(
        "/api/notes", json={"title": "Snark", "body": "Body mentioning snarky wombat."}
    ).json()
    try:
        resp = client.post("/api/search", json={"query": "wombat", "source_type": "pdf"})
        assert resp.status_code == 200
        assert all(h["source_type"] != "note" for h in resp.json()["hits"])
    finally:
        client.delete(f"/api/notes/{created['id']}")
