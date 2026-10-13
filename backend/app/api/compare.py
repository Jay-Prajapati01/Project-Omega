"""Cross-source comparison endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import compare

router = APIRouter(prefix="/compare", tags=["compare"])


class CompareRequest(BaseModel):
    source_id_a: str = Field(..., description="First source id")
    source_id_b: str = Field(..., description="Second source id")


@router.post("")
async def compare_sources(payload: CompareRequest) -> dict:
    """Compare two indexed sources: similarities, differences, contradictions."""
    if payload.source_id_a == payload.source_id_b:
        raise HTTPException(status_code=400, detail="Choose two different sources")
    return await compare.compare(payload.source_id_a, payload.source_id_b)
