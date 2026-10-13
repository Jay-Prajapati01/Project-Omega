"""Exercise two verified identities against real local persistence and Qdrant.

Only the external token verifier is replaced. Files, metadata, graph and vector
operations use their real implementations in temporary storage.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.tenant import Scope, current_scope
from app.models.schemas import SourceItem
from app.services import file_storage, graph, store, vectorstore

ALICE = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
BOB = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"


@contextmanager
def as_user(user):
    token = current_scope.set(Scope(user, user))
    try:
        yield
    finally:
        current_scope.reset(token)


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_enabled", True)
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "local")
    monkeypatch.setattr(cfg, "data_dir", str(tmp_path))
    monkeypatch.setattr(cfg, "qdrant_collection", "account-test")
    monkeypatch.setattr(vectorstore, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(vectorstore, "_ready", False)

    async def verify(_client, _url, *, headers):
        user = {"Bearer alice": ALICE, "Bearer bob": BOB}.get(headers["Authorization"])
        return SimpleNamespace(status_code=200 if user else 401, json=lambda: {"id": user})

    from app.main import create_app
    with patch("httpx.AsyncClient.get", verify):
        yield TestClient(create_app())


def test_anonymous_and_invalid_sessions_cannot_read_or_write(accounts):
    for path in ["/api/notes", "/api/sources", "/api/graph", "/api/stats", "/api/timeline"]:
        assert accounts.get(path).status_code == 401
        assert accounts.get(path, headers={"Authorization": "Bearer forged"}).status_code == 401
    assert accounts.post("/api/notes", json={"title": "Forbidden"}).status_code == 401


def test_notes_are_private_even_with_forged_ownership(accounts):
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob", "X-Tenant-ID": ALICE, "X-User-ID": ALICE}
    note = accounts.post("/api/notes", headers=alice, json={"title": "Alice private note", "body": "secret"}).json()
    assert accounts.get("/api/notes", headers=bob).json() == []
    assert accounts.delete(f"/api/notes/{note['id']}", headers=bob).status_code == 404
    assert accounts.get("/api/notes", headers=alice).json()[0]["body"] == "secret"
    accounts.post("/api/notes", headers=bob, json={"title": "Bob private note"})
    assert len(accounts.get("/api/notes", headers=alice).json()) == 1
    assert accounts.get("/api/notes", headers=bob).json()[0]["title"] == "Bob private note"


def test_sources_files_graph_and_conversations_are_private(accounts):
    with as_user(ALICE):
        path = file_storage.save_file("shared-id", b"Alice file", "document", "note.txt")
        store.add_source(SourceItem(source_id="shared-id", source_type="document", title="Alice source", file_path=path, mime_type="text/plain"))
        graph._save({"nodes": {"Alice": 1}, "edges": []})
        store.save_conversation_turn("conversation-a", {"question": "Alice question", "answer": "Alice answer"})
    bob = {"Authorization": "Bearer bob"}
    for suffix in ["", "/view", "/download"]:
        assert accounts.get("/api/sources/shared-id" + suffix, headers=bob).status_code == 404
    assert accounts.delete("/api/sources/shared-id", headers=bob).status_code == 404
    assert accounts.get("/api/chat/conversations/conversation-a", headers=bob).status_code == 404
    with as_user(BOB):
        assert graph._load() == {"nodes": {}, "edges": []}
        assert file_storage.get_file_path(path) is None
        file_storage.save_file("shared-id", b"Bob file", "document", "note.txt")
    with as_user(ALICE):
        assert file_storage.get_file_path(path).read_bytes() == b"Alice file"
        assert graph._load()["nodes"] == {"Alice": 1}
    response = accounts.get("/api/sources/shared-id/download", headers={"Authorization": "Bearer alice"})
    assert response.content == b"Alice file"


def test_vectors_cannot_be_read_overwritten_or_deleted_across_accounts(accounts):
    cfg = get_settings()
    vector = [1.0] + [0.0] * (cfg.embedding_dim_for_model - 1)
    for user, text in [(ALICE, "Alice vector"), (BOB, "Bob vector")]:
        with as_user(user):
            vectorstore.upsert_chunks([vector], [{"source_id": "same-source", "chunk_index": 0, "text": text}])
    with as_user(ALICE):
        assert vectorstore.count() == 1
        assert vectorstore.search(vector, 10)[0]["text"] == "Alice vector"
        vectorstore.delete_by_source_id("same-source")
        assert vectorstore.count() == 0
    with as_user(BOB):
        assert vectorstore.count() == 1
        assert vectorstore.search(vector, 10)[0]["text"] == "Bob vector"
