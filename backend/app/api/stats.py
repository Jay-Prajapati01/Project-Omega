"""Dashboard statistics endpoint."""
from fastapi import APIRouter

from app.models.schemas import RecentQuery, SourceItem, StatsResponse
from app.services import file_storage, store, vectorstore

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def stats() -> StatsResponse:
    """Return high-level counts and recent activity for the dashboard."""
    # Get real storage stats
    file_count, storage_bytes = file_storage.storage_stats()
    
    return StatsResponse(
        indexed_chunks=vectorstore.count(),
        total_sources=store.total_sources(),
        sources_by_type=store.counts_by_type(),
        total_files_stored=file_count,
        total_storage_bytes=storage_bytes,
        recent_sources=[SourceItem(**s) for s in store.recent_sources()],
        recent_searches=[RecentQuery(**q) for q in store.recent_searches()],
        recent_questions=[RecentQuery(**q) for q in store.recent_questions()],
        knowledge_growth=store.chunks_by_day(),
    )
