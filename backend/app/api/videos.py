"""YouTube video ingestion and listing endpoints."""
import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.models.schemas import (
    VideoProcessRequest,
    VideoProcessResponse,
)
from app.services import chunking, embeddings, graph, rag, store, vectorstore, youtube
from app.services.sse import public_error, sse

logger = get_logger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/process", response_model=VideoProcessResponse)
async def process_video(payload: VideoProcessRequest) -> VideoProcessResponse:
    from app.services.commerce import reserve
    reserve("youtube")
    """Ingest a YouTube video: metadata, transcript, summary, embeddings."""
    try:
        metadata = youtube.fetch_metadata(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Metadata fetch failed")
        raise HTTPException(status_code=502, detail="Failed to fetch metadata") from exc

    transcript = youtube.fetch_transcript(metadata.video_id)
    if not transcript:
        raise HTTPException(status_code=422, detail="No transcript available")

    from app.services import ingest
    item = await ingest.ingest_text(
        text=transcript,
        source_id=metadata.video_id,
        source_type="youtube",
        title=metadata.title,
        channel=metadata.channel,
        thumbnail=metadata.thumbnail,
        url=payload.url,
    )

    return VideoProcessResponse(
        video_id=metadata.video_id,
        metadata=metadata,
        summary=item.summary,
        key_topics=item.key_topics,
        chunks_indexed=item.chunks_indexed,
    )


@router.post("/process/stream")
async def process_video_stream(payload: VideoProcessRequest):
    from app.services.commerce import reserve
    reserve("youtube")
    """Ingest a YouTube video with real-time SSE progress events."""

    async def event_generator():
        t0 = time.time()

        def ms():
            return round((time.time() - t0) * 1000)

        summary = ""
        topics: list[str] = []

        try:
            # ── Step 1: Validate URL ──────────────────────────────────────
            yield sse("step_start", {"step": 1, "total_steps": 7, "name": "Validating URL", "description": "Extracting video ID from URL..."})
            try:
                video_id = youtube.extract_video_id(payload.url)
                yield sse("step_complete", {"step": 1, "duration_ms": ms(), "video_id": video_id})
            except ValueError as exc:
                yield sse("step_fail", {"step": 1, "error": str(exc)})
                return

            # ── Step 2: Fetch Metadata ────────────────────────────────────
            yield sse("step_start", {"step": 2, "total_steps": 7, "name": "Fetching Metadata", "description": "Getting video info via yt-dlp..."})
            try:
                metadata = youtube.fetch_metadata(payload.url)
                yield sse("step_complete", {
                    "step": 2, "duration_ms": ms(),
                    "thumbnail": metadata.thumbnail, "title": metadata.title,
                    "channel": metadata.channel, "duration": metadata.duration,
                })
                yield sse("preview", {"type": "thumbnail", "thumbnail": metadata.thumbnail, "title": metadata.title, "channel": metadata.channel})
            except Exception as exc:
                logger.exception("Video metadata fetch failed")
                yield sse("step_fail", {"step": 2, "error": public_error(exc, "Metadata fetch")})
                return

            # ── Step 3: Fetch Transcript ──────────────────────────────────
            yield sse("step_start", {"step": 3, "total_steps": 7, "name": "Fetching Transcript", "description": "Trying YouTube Transcript API..."})
            try:
                transcript = youtube.fetch_transcript(video_id)
                if not transcript:
                    yield sse("step_fail", {"step": 3, "error": "No transcript available"})
                    return
                preview_text = transcript[:300] + ("..." if len(transcript) > 300 else "")
                yield sse("step_complete", {"step": 3, "duration_ms": ms(), "chars": len(transcript)})
                yield sse("preview", {"type": "transcript", "text": preview_text, "chars": len(transcript)})
            except ValueError as exc:
                yield sse("step_fail", {"step": 3, "error": str(exc)})
                return

            # ── Step 4: Generate Summary (streaming) ──────────────────────
            yield sse("step_start", {"step": 4, "total_steps": 7, "name": "Generating Summary", "description": "AI summarizing content using Ollama..."})
            summary_tokens: list[str] = []
            try:
                async for token in rag.summarize_stream(transcript):
                    summary_tokens.append(token)
                    yield sse("stream_token", {"step": 4, "type": "summary", "token": token})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Streaming summary failed, falling back: %s", exc)
                try:
                    summary, topics = await rag.summarize(transcript)
                except Exception:
                    summary = transcript[:500]
                    topics = []
                yield sse("step_complete", {"step": 4, "duration_ms": ms(), "summary": summary, "topics": topics})
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
                yield sse("step_complete", {"step": 4, "duration_ms": ms(), "summary": summary, "topics": topics})

            # ── Step 5: Chunk Content ─────────────────────────────────────
            yield sse("step_start", {"step": 5, "total_steps": 7, "name": "Chunking Content", "description": "Splitting text into indexable chunks..."})
            chunks = chunking.chunk_text(transcript)
            if not chunks:
                yield sse("step_fail", {"step": 5, "error": "No indexable text content"})
                return
            yield sse("step_complete", {"step": 5, "duration_ms": ms(), "chunk_count": len(chunks)})

# ── Step 6: Create Embeddings ─────────────────────────────────
            yield sse("step_start", {"step": 6, "total_steps": 7, "name": "Creating Embeddings", "description": "Generating vector embeddings..."})
            vectors: list[list[float]] = []
            for i, chunk in enumerate(chunks):
                try:
                    vec = await embeddings.embed_text(chunk)
                except Exception as exc:  # noqa: BLE001
                    # Never index zero-vectors - they poison search results.
                    yield sse("step_fail", {"step": 6, "error": f"Embedding failed on chunk {i + 1}/{len(chunks)} ({type(exc).__name__})"})
                    return
                vectors.append(vec)
                pct = int(((i + 1) / len(chunks)) * 100)
                yield sse("step_progress", {"step": 6, "progress": pct, "sub_text": f"Chunk {i + 1}/{len(chunks)}"})
            yield sse("step_complete", {"step": 6, "duration_ms": ms(), "vectors_count": len(vectors)})

            # ── Step 7: Index & Graph ─────────────────────────────────────
            yield sse("step_start", {"step": 7, "total_steps": 7, "name": "Indexing & Graph", "description": "Storing in Qdrant and extracting knowledge graph..."})
            payloads = [
                {"text": chunk, "source_id": video_id, "source_type": "youtube", "title": metadata.title, "chunk_index": i, "channel": metadata.channel, "thumbnail": metadata.thumbnail, "url": payload.url}
                for i, chunk in enumerate(chunks)
            ]
            vectorstore.ensure_collection()
            # Remove any previous chunks for this source so re-ingests
            # never create duplicates.
            try:
                vectorstore.delete_by_source_id(video_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("delete_by_source_id failed for %s: %s", video_id, exc)
            indexed = vectorstore.upsert_chunks(vectors, payloads)

            try:
                triples = await graph.extract_relations(transcript)
                graph.add_triples(triples, video_id, "youtube", metadata.title)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Graph extraction failed: %s", exc)

            yield sse("step_complete", {"step": 7, "duration_ms": ms()})

            # ── Store source record ───────────────────────────────────────
            from app.models.schemas import SourceItem
            item = SourceItem(
                source_id=video_id,
                source_type="youtube",
                title=metadata.title,
                channel=metadata.channel,
                thumbnail=metadata.thumbnail,
                summary=summary,
                key_topics=topics,
                chunks_indexed=indexed,
                url=payload.url,
            )
            store.add_source(item)

            yield sse("complete", {"source_id": video_id, "title": metadata.title, "summary": summary, "key_topics": topics, "chunks_indexed": indexed})
        except Exception as exc:
            logger.exception("Videos stream failed")
            yield sse("step_fail", {"step": 0, "error": public_error(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
