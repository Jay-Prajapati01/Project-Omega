"""Knowledge graph endpoint."""
from fastapi import APIRouter

from app.services import graph

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
async def get_graph() -> dict:
    """Return all nodes and edges in the knowledge graph."""
    return graph.get_graph()


@router.post("/rebuild")
async def rebuild_graph() -> dict:
    """Rebuild graph provenance from the current user's indexed sources."""
    return await graph.rebuild_from_saved_sources()
