"""Lightweight JSON-backed metadata store for ingested sources and activity.

This complements Qdrant (which stores vectors) by keeping human-facing
metadata: the list of ingested sources and recent search/question activity.
It is intentionally simple (single JSON file) and can be swapped for
PostgreSQL in a later phase without changing the API layer.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.logging import get_logger
from app.core.tenant import cloud, authenticated, data_directory
from app.models.schemas import RecentQuery, SourceItem
from app.services import cloud_db

logger = get_logger(__name__)
_lock = cloud_db.StoreLock()
_MAX_RECENT = 20
_CACHE: dict | None = None
_CACHE_PATH: Path | None = None
_CACHE_VALID = False


def _path() -> Path:
    data_dir = data_directory()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "store.json"


def _load() -> dict:
    if cloud():
        return cloud_db.load("store", {"sources": [], "searches": [], "questions": [], "notes": []})
    if authenticated():
        path = _path()
        if not path.exists():
            return {"sources": [], "searches": [], "questions": [], "notes": []}
        # Do not share mutable process-global caches across account requests.
        return json.loads(path.read_text())
    global _CACHE, _CACHE_PATH, _CACHE_VALID
    path = _path()
    
    # Use cache if path hasn't changed
    if _CACHE_VALID and _CACHE_PATH == path and _CACHE is not None:
        return _CACHE
    
    if not path.exists():
        _CACHE = {"sources": [], "searches": [], "questions": []}
        _CACHE_PATH = path
        _CACHE_VALID = True
        return _CACHE
    try:
        _CACHE = json.loads(path.read_text())
        _CACHE_PATH = path
        _CACHE_VALID = True
        return _CACHE
    except (json.JSONDecodeError, OSError):
        logger.warning("Store file unreadable; starting fresh")
        _CACHE = {"sources": [], "searches": [], "questions": []}
        _CACHE_PATH = path
        _CACHE_VALID = True
        return _CACHE


def _save(data: dict) -> None:
    if cloud():
        cloud_db.save("store", data)
        return
    global _CACHE, _CACHE_VALID
    path = _path()
    # Atomic write: a crash mid-write must never truncate store.json.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, default=str, indent=2))
    tmp.replace(path)
    if not authenticated():
        _CACHE = data
        _CACHE_VALID = True


def invalidate_cache() -> None:
    """Invalidate the cache to force reload from disk."""
    global _CACHE_VALID
    _CACHE_VALID = False


def add_source(item: SourceItem) -> None:
    with _lock:
        data = _load()
        # de-duplicate by source_id
        data["sources"] = [
            s for s in data["sources"] if s.get("source_id") != item.source_id
        ]
        data["sources"].insert(0, json.loads(item.model_dump_json()))
        _save(data)


def add_search(text: str) -> None:
    _add_activity("searches", text)


def add_question(text: str) -> None:
    _add_activity("questions", text)


def _add_activity(key: str, text: str) -> None:
    with _lock:
        data = _load()
        entry = json.loads(RecentQuery(text=text).model_dump_json())
        if cloud():
            from app.core.tenant import scope
            entry["job_id"] = scope().job_id
            if any(row.get("job_id") == entry["job_id"] for row in data[key]):
                return
        data[key].insert(0, entry)
        data[key] = data[key][:_MAX_RECENT]
        _save(data)


def list_sources(source_type: str | None = None) -> list[dict]:
    data = _load()
    sources = data.get("sources", [])
    if source_type:
        sources = [s for s in sources if s.get("source_type") == source_type]
    return sources


def recent_sources(limit: int = 8) -> list[dict]:
    return _load().get("sources", [])[:limit]


def recent_searches(limit: int = 8) -> list[dict]:
    return _load().get("searches", [])[:limit]


def recent_questions(limit: int = 8) -> list[dict]:
    return _load().get("questions", [])[:limit]


def counts_by_type() -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in _load().get("sources", []):
        st = s.get("source_type", "unknown")
        counts[st] = counts.get(st, 0) + 1
    return counts


def total_sources() -> int:
    return len(_load().get("sources", []))


def chunks_by_day() -> list[dict]:
    """Return chunk counts grouped by day for the last 7 days."""
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict

    sources = _load().get("sources", [])
    day_chunks: dict[str, int] = defaultdict(int)

    for s in sources:
        created = s.get("created_at")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            day_key = dt.strftime("%Y-%m-%d")
            chunks = s.get("chunks_indexed", 0)
            day_chunks[day_key] += chunks
        except (ValueError, TypeError):
            continue

    today = datetime.now(timezone.utc).date()
    result = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        label = day.strftime("%a")
        result.append({
            "date": day_key,
            "name": label,
            "chunks": day_chunks.get(day_key, 0),
        })
    return result


# --- Notes (Workspace) -------------------------------------------------


def list_notes() -> list[dict]:
    return _load().get("notes", [])


def add_note(title: str, body: str) -> dict:
    import uuid
    from datetime import datetime, timezone

    with _lock:
        data = _load()
        data.setdefault("notes", [])
        note = {
            "id": str(uuid.uuid4()),
            "title": title,
            "body": body,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data["notes"].insert(0, note)
        _save(data)
        return note


def delete_note(note_id: str) -> bool:
    with _lock:
        data = _load()
        notes = data.get("notes", [])
        new_notes = [n for n in notes if n.get("id") != note_id]
        data["notes"] = new_notes
        _save(data)
        return len(new_notes) != len(notes)


def delete_source(source_id: str) -> bool:
    """Delete a source from the store. Returns True if deleted."""
    with _lock:
        data = _load()
        sources = data.get("sources", [])
        new_sources = [s for s in sources if s.get("source_id") != source_id]
        data["sources"] = new_sources
        _save(data)
        return len(new_sources) != len(sources)


def get_conversation(conversation_id: str) -> dict | None:
    from app.core.tenant import scope
    user = scope().user_id if authenticated() else "local"
    return next((c for c in _load().get("conversations", [])
                 if c["id"] == conversation_id and c["user_id"] == user), None)


def save_conversation_turn(conversation_id: str, response: dict) -> None:
    from app.core.tenant import scope
    from datetime import datetime, timezone
    user = scope().user_id if authenticated() else "local"
    job_id = scope().job_id if cloud() else None
    with _lock:
        data = _load()
        conversations = data.setdefault("conversations", [])
        conversation = next((c for c in conversations if c["id"] == conversation_id and c["user_id"] == user), None)
        if conversation is None:
            conversation = {"id": conversation_id, "user_id": user, "turns": [], "title": response["question"][:80]}
            conversations.append(conversation)
        if job_id and any(t.get("job_id") == job_id for t in conversation["turns"]):
            return
        conversation["turns"].append({"job_id": job_id, "response": response})
        conversation["turns"] = conversation["turns"][-50:]
        conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)
