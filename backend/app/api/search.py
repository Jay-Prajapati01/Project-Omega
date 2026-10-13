"""Semantic search endpoint."""
import time

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.schemas import SearchHit, SearchRequest, SearchResponse
from app.services import relevance, store

router = APIRouter(prefix="/search", tags=["search"])


def _is_http_url(value: str | None) -> bool:
    """Only http(s) strings are safe to use as links."""
    return bool(value) and str(value).startswith(("http://", "https://"))


def _resolve_hit_url(hit: dict, source_type: str, source_id: str, settings) -> str | None:
    """Resolve a safe URL for a search hit.

    Never falls back to `channel`/`file_path` unless they are real http(s) URLs —
    `channel` usually holds a channel NAME (e.g. "MrBeast"), not a link.
    """
    url = hit.get("url") or ""
    if _is_http_url(url):
        return url
    if source_type in ("pdf", "document", "audio"):
        return f"{settings.api_prefix}/sources/{source_id}/download" if source_id else None
    channel = hit.get("channel") or ""
    if _is_http_url(channel):
        return channel
    return None


@router.post("", response_model=SearchResponse)
async def search(payload: SearchRequest) -> SearchResponse:
    settings = get_settings()
    top_k = payload.top_k or settings.top_k
    query = payload.query

    # Blank queries have nothing to match: answer gracefully without
    # embedding an empty string (which would return arbitrary chunks).
    if not query:
        return SearchResponse(
            query=query,
            hits=[],
            search_time_ms=0,
            chunks_searched=0,
            sources_searched=0,
        )

    from app.services.commerce import CommerceError, reserve
    try:
        reserve("search")
    except CommerceError as exc:
        from fastapi import HTTPException
        raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None

    store.add_search(query)
    start = time.time()
    raw_hits, chunks_scanned = await relevance.search(
        query, limit=top_k, source_type=payload.source_type,
    )
    search_time_ms = int((time.time() - start) * 1000)
    hits = []
    for hit in raw_hits:
        source_id = hit.get("source_id", "")
        source_type = hit.get("source_type", "unknown")
        url = _resolve_hit_url(hit, source_type, source_id, settings)

        hits.append(
            SearchHit(
                score=hit["score"],
                text=hit.get("text", ""),
                source_id=source_id,
                source_type=source_type,
                title=hit.get("title"),
                url=url,
                thumbnail=hit.get("thumbnail"),
            )
        )

    return SearchResponse(
        query=query,
        hits=hits,
        search_time_ms=search_time_ms,
        chunks_searched=chunks_scanned,
        sources_searched=len({h.source_id for h in hits}),
    )
