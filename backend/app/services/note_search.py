"""Plain-text matching for Workspace notes.

Notes are not embedded, so they are matched by keyword instead of vectors.
Shared by the search endpoint and chat/RAG so both reach the same data.
"""
from __future__ import annotations

from app.services import store


def note_hits(query: str, source_type: str | None = None) -> list[dict]:
    """Return matching Workspace notes as hit dicts (source_type="note").

    Returns an empty list when `source_type` is set to anything but "note"
    so callers can pass their own source_type filter straight through.
    """
    if source_type and source_type != "note":
        return []
    needle = query.lower()
    tokens = [t for t in needle.split() if len(t) >= 2]
    hits: list[dict] = []
    for note in store.list_notes():
        note_id = str(note.get("id", ""))
        if not note_id:
            continue
        title = str(note.get("title") or "")
        body = str(note.get("body") or "")
        haystack_title = title.lower()
        haystack_body = body.lower()
        if needle and needle in haystack_title:
            score = 0.95
        elif needle and needle in haystack_body:
            score = 0.85
        elif tokens and all(t in haystack_title or t in haystack_body for t in tokens):
            score = 0.8 if tokens[0] in haystack_title else 0.7
        else:
            continue
        text = body.strip() or title
        if len(text) > 500:
            text = text[:500].rstrip() + "…"
        hits.append(
            {
                "score": score,
                "text": text,
                "source_id": note_id,
                "source_type": "note",
                "title": title or "Untitled note",
                "url": None,
                "thumbnail": None,
            }
        )
    return hits
