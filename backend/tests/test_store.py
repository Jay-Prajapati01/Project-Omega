"""Tests for the JSON-backed store using a temp data dir."""
import importlib

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.core import config

    config.get_settings.cache_clear()
    from app.services import store as store_module

    importlib.reload(store_module)
    return store_module


def test_add_and_list_notes(store):
    note = store.add_note("Title", "Body")
    assert note["id"]
    notes = store.list_notes()
    assert len(notes) == 1
    assert notes[0]["title"] == "Title"


def test_delete_note(store):
    note = store.add_note("T", "B")
    assert store.delete_note(note["id"]) is True
    assert store.list_notes() == []
    assert store.delete_note("missing") is False


def test_recent_activity(store):
    store.add_search("query one")
    store.add_question("question one")
    assert store.recent_searches()[0]["text"] == "query one"
    assert store.recent_questions()[0]["text"] == "question one"
