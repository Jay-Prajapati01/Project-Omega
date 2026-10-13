"""Memory timeline endpoint: sources grouped by recency."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.services import store

router = APIRouter(prefix="/timeline", tags=["timeline"])


def _bucket(created: datetime, now: datetime) -> str:
    delta = now - created
    if created.date() == now.date():
        return "Today"
    if delta < timedelta(days=2) and created.date() == (now.date() - timedelta(days=1)):
        return "Yesterday"
    if delta < timedelta(days=7):
        return "This week"
    if delta < timedelta(days=30):
        return "This month"
    return "Earlier"


@router.get("")
async def timeline() -> dict:
    """Return ingested sources grouped into recency buckets."""
    now = datetime.now(timezone.utc)
    order = ["Today", "Yesterday", "This week", "This month", "Earlier"]
    groups: dict[str, list] = {k: [] for k in order}

    for s in store.list_sources():
        raw = s.get("created_at")
        try:
            created = datetime.fromisoformat(str(raw))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            created = now
        bucket = _bucket(created, now)
        groups[bucket].append(
            {
                "source_id": s.get("source_id"),
                "source_type": s.get("source_type"),
                "title": s.get("title"),
                "created_at": raw,
            }
        )

    return {"groups": [{"label": k, "items": groups[k]} for k in order if groups[k]]}
