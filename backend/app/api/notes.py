"""Workspace notes endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_key
from app.services import store

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body: str = ""


@router.get("")
async def list_notes() -> list[dict]:
    return store.list_notes()


@router.post("", dependencies=[Depends(require_key)])
async def create_note(payload: NoteRequest) -> dict:
    return store.add_note(payload.title, payload.body)


@router.delete("/{note_id}", dependencies=[Depends(require_key)])
async def delete_note(note_id: str) -> dict:
    if not store.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": note_id}
