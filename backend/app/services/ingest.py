"""Shared ingestion pipeline used by every source type.

Given already-extracted text and source metadata, this: summarizes,
chunks, embeds, upserts to Qdrant, extracts knowledge-graph triples, and
records the source in the store. Each source-specific service (youtube, pdf,
instagram, ...) only needs to extract text + metadata, then call
`ingest_text`.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from app.core.logging import get_logger
from app.models.schemas import SourceItem
from app.services import (
    chunking,
    embeddings,
    graph,
    rag,
    store,
    vectorstore,
)

logger = get_logger(__name__)

# Type alias: emit("step_start", {...}) or await emit("step_start", {...})
ProgressCallback = Callable[[str, dict[str, Any]], Any]


async def ingest_text(
    *,
    text: str,
    source_id: str,
    source_type: str,
    title: str | None = None,
    channel: str | None = None,
    thumbnail: str | None = None,
    url: str | None = None,
    file_path: str | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
    structured_chunks: list[dict] | None = None,
    page_count: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> SourceItem:
    """Run the full pipeline for a piece of text and return the stored item.

    If on_progress is provided, it is called with (event_name, data_dict)
    at each pipeline step.  The callback may be sync or async.
    """

    async def emit(event: str, data: dict[str, Any]) -> None:
        if on_progress is not None:
            result = on_progress(event, data)
            if hasattr(result, "__await__"):
                await result

    # ── Step 4: Generate Summary (streaming tokens) ──────────────────
    await emit("step_start", {"step": 4, "total_steps": 7, "name": "Generating Summary", "description": "AI summarizing content..."})

    summary_tokens: list[str] = []
    try:
        async for token in rag.summarize_stream(text):
            summary_tokens.append(token)
            await emit("stream_token", {"step": 4, "type": "summary", "token": token})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Streaming summary failed, falling back: %s", exc)
        summary, topics = await rag.summarize(text)
        await emit("step_complete", {"step": 4, "duration_ms": 0, "summary": summary, "topics": topics})
    else:
        raw = "".join(summary_tokens)
        try:
            start, end = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[start : end + 1])
            summary = data.get("summary", "").strip()
            topics = list(data.get("topics", []))
        except (ValueError, json.JSONDecodeError):
            summary = raw.strip()
            topics = []
        await emit("step_complete", {"step": 4, "duration_ms": 0, "summary": summary, "topics": topics})

    # ── Step 5: Chunk Content ─────────────────────────────────────────
    await emit("step_start", {"step": 5, "total_steps": 7, "name": "Chunking Content", "description": "Splitting text into indexable chunks..."})

    chunks = [chunk["text"] for chunk in structured_chunks] if structured_chunks else chunking.chunk_text(text)
    if not chunks:
        raise ValueError("No indexable text content")

    await emit("step_complete", {"step": 5, "duration_ms": 0, "chunk_count": len(chunks)})

    # ── Step 6: Create Embeddings ─────────────────────────────────────
    await emit("step_start", {"step": 6, "total_steps": 7, "name": "Creating Embeddings", "description": "Generating vector embeddings..."})

    vectors: list[list[float]] = []
    for offset in range(0, len(chunks), 32):
        vectors.extend(await embeddings.embed_texts(chunks[offset:offset + 32]))
        await emit("step_progress", {"step": 6, "progress": int(len(vectors) / len(chunks) * 100)})

    await emit("step_complete", {"step": 6, "duration_ms": 0, "vectors_count": len(vectors)})

    payloads = [
        {
            **({k: v for k, v in structured_chunks[i].items() if k != "text"} if structured_chunks else {}),
            "text": chunk,
            "source_id": source_id,
            "source_type": source_type,
            "title": title,
            "chunk_index": i,
            "channel": channel,
            "thumbnail": thumbnail,
            "url": url,
            "file_path": file_path,
            "file_name": file_name,
        }
        for i, chunk in enumerate(chunks)
    ]

    # ── Step 7: Index & Graph ─────────────────────────────────────────
    await emit("step_start", {"step": 7, "total_steps": 7, "name": "Indexing & Graph", "description": "Storing in Qdrant and extracting knowledge graph..."})

    vectorstore.ensure_collection()
    
    # Delete existing chunks for this source_id to prevent duplicates
    try:
        deleted = vectorstore.delete_by_source_id(source_id)
        if deleted > 0:
            logger.info("Deleted %d existing chunks for %s before re-indexing", deleted, source_id)
    except Exception as exc:
        from app.core.tenant import cloud
        if cloud():
            raise
        logger.warning("Failed to cleanup old chunks for %s: %s", source_id, exc)
    
    indexed = vectorstore.upsert_chunks(vectors, payloads)

    # Best-effort knowledge graph extraction (non-fatal).
    try:
        triples = await graph.extract_relations(text)
        graph.replace_triples(triples, source_id, source_type, title)
    except Exception as exc:  # noqa: BLE001
        from app.core.tenant import cloud
        if cloud():
            raise
        logger.warning("Graph extraction failed for %s: %s", source_id, exc)

    await emit("step_complete", {"step": 7, "duration_ms": 0})

    item = SourceItem(
        source_id=source_id,
        source_type=source_type,
        title=title,
        channel=channel,
        thumbnail=thumbnail,
        summary=summary,
        key_topics=topics,
        chunks_indexed=indexed,
        url=url,
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        page_count=page_count,
    )
    store.add_source(item)
    logger.info("Ingested %s:%s (%d chunks)", source_type, source_id, indexed)

    await emit("complete", {
        "summary": summary,
        "key_topics": topics,
        "chunks_indexed": indexed,
    })

    return item
