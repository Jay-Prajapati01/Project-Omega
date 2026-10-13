"""Contact form endpoint: public, validated, and persisted (UI contact flow)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client(hermetic):
    return TestClient(app)


@pytest.fixture
def store(tmp_path):
    """Point the file store at a temp dir; disable Supabase for JSONL tests."""
    settings = get_settings()
    previous = (
        settings.data_dir,
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_db_url,
    )
    settings.data_dir = str(tmp_path)
    settings.supabase_url = ""
    settings.supabase_service_role_key = ""
    settings.supabase_db_url = ""
    yield tmp_path / "contact_submissions.jsonl"
    (
        settings.data_dir,
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.supabase_db_url,
    ) = previous


@pytest.fixture
def supabase_store(store, monkeypatch):
    """Configure a mocked Supabase REST insert for contact storage."""
    settings = get_settings()
    previous = (settings.supabase_url, settings.supabase_service_role_key)
    settings.supabase_url = "https://example.supabase.co"
    settings.supabase_service_role_key = "service-test-key"
    inserted: list[dict] = []
    monkeypatch.setattr("app.api.contact._insert_supabase", inserted.append)
    yield inserted
    (settings.supabase_url, settings.supabase_service_role_key) = previous


def _payload(**over):
    base = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "topic": "General",
        "message": "I would like to know more about MindMesh workspaces.",
    }
    base.update(over)
    return base


def test_valid_submission_accepted_and_stored_in_file(client, store):
    resp = client.post("/api/contact", json=_payload(company="Analytical Engines"))
    assert resp.status_code == 202
    assert resp.json() == {"status": "received"}
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Ada Lovelace"
    assert row["email"] == "ada@example.com"
    assert row["company"] == "Analytical Engines"
    assert row["topic"] == "General"
    assert row["message"].startswith("I would like")
    assert row["received_at"]


def test_company_is_optional(client, store):
    resp = client.post("/api/contact", json=_payload())
    assert resp.status_code == 202


@pytest.mark.parametrize(
    "bad",
    [
        _payload(email="not-an-email"),
        _payload(message="too short"),
        _payload(topic="Sales"),
        _payload(name="   "),
        _payload(message="x" * 2001),
    ],
)
def test_invalid_submissions_rejected(client, store, bad):
    assert client.post("/api/contact", json=bad).status_code == 422


def test_contact_stays_public_without_a_session(modal_client, store):
    """Cloud mode demands bearer tokens everywhere except health — and contact."""
    resp = modal_client.post("/api/contact", json=_payload())
    assert resp.status_code == 202


def test_supabase_insert_used_when_configured(client, supabase_store, store):
    resp = client.post("/api/contact", json=_payload(company="Analytical Engines"))
    assert resp.status_code == 202
    assert len(supabase_store) == 1
    row = supabase_store[0]
    assert row["name"] == "Ada Lovelace"
    assert row["email"] == "ada@example.com"
    assert row["company"] == "Analytical Engines"
    assert row["topic"] == "General"
    # Supabase path succeeded: the local file store must stay untouched.
    assert not store.exists()


def test_falls_back_to_file_when_supabase_is_down(
    client, supabase_store, store, monkeypatch
):
    def _boom(payload):
        raise OSError("network unreachable")

    monkeypatch.setattr("app.api.contact._insert_supabase", _boom)
    resp = client.post("/api/contact", json=_payload())
    assert resp.status_code == 202
    assert store.exists()
