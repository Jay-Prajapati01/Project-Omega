"""Instagram ingestion endpoint."""
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.models.schemas import SourceItem
from app.services import chunking, embeddings, graph, rag, store, vectorstore, instagram
from app.services.sse import public_error, sse

logger = get_logger(__name__)
router = APIRouter(prefix="/instagram", tags=["instagram"])


class InstagramRequest(BaseModel):
    url: str = Field(..., description="Instagram post or reel URL")


@router.post("/process", response_model=SourceItem)
async def process_instagram(payload: InstagramRequest) -> SourceItem:
    from app.services.commerce import reserve
    reserve("instagram")
    """Ingest an Instagram post/reel: caption, OCR, and speech."""
    try:
        post = instagram.fetch_post(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Instagram fetch failed")
        raise HTTPException(status_code=502, detail="Failed to fetch post") from exc

    if not post["text"]:
        raise HTTPException(status_code=422, detail="No extractable content")

    from app.services import ingest
    return await ingest.ingest_text(
        text=post["text"], source_id=post["shortcode"], source_type="instagram",
        title=post["title"], channel=post["owner"], thumbnail=post["thumbnail"],
        url=payload.url,
    )


@router.post("/process/stream")
async def process_instagram_stream(payload: InstagramRequest):
    from app.services.commerce import reserve
    reserve("instagram")
    """Ingest an Instagram post/reel with real-time SSE progress events."""

    async def event_generator():
        import json as _json
        t0 = time.time()
        def ms(): return round((time.time() - t0) * 1000)

        summary = ""
        topics: list[str] = []

        try:
            # Step 1: Validate URL
            yield sse("step_start", {"step": 1, "total_steps": 7, "name": "Validating URL", "description": "Checking Instagram URL..."})
            try:
                shortcode = instagram.extract_shortcode(payload.url)
                yield sse("step_complete", {"step": 1, "duration_ms": ms(), "shortcode": shortcode})
            except ValueError as exc:
                yield sse("step_fail", {"step": 1, "error": str(exc)})
                return

            # Step 2: Render Page
            yield sse("step_start", {"step": 2, "total_steps": 7, "name": "Rendering Page", "description": "Opening post in headless browser via Playwright..."})
            try:
                post = instagram.fetch_post(payload.url)
                yield sse("step_complete", {"step": 2, "duration_ms": ms(), "username": post.get("owner", "")})
            except Exception as exc:
                logger.exception("Instagram post fetch failed")
                yield sse("step_fail", {"step": 2, "error": public_error(exc, "Post fetch")})
                return

            if not post["text"]:
                yield sse("step_fail", {"step": 2, "error": "No extractable content found"})
                return

            # Step 3: Extract Caption
            yield sse("step_start", {"step": 3, "total_steps": 7, "name": "Extracting Caption", "description": "Parsing caption and username..."})
            yield sse("step_complete", {"step": 3, "duration_ms": ms(), "caption_preview": (post.get("caption") or "")[:300]})

            # Step 4: Extract Media
            yield sse("step_start", {"step": 4, "total_steps": 7, "name": "Extracting Media", "description": "Downloading images/video..."})
            yield sse("step_complete", {"step": 4, "duration_ms": ms(), "thumbnail": post.get("thumbnail")})

            # Step 5: Extract Text
            yield sse("step_start", {"step": 5, "total_steps": 7, "name": "Extracting Text", "description": "Running OCR and Whisper..."})
            yield sse("step_complete", {"step": 5, "duration_ms": ms(), "chars": len(post["text"])})
            yield sse("preview", {"type": "transcript", "text": post["text"][:300], "chars": len(post["text"])})

            # Step 6: Generate Summary
            yield sse("step_start", {"step": 6, "total_steps": 7, "name": "Generating Summary", "description": "AI summarizing content using Ollama..."})
            summary_tokens = []
            try:
                async for token in rag.summarize_stream(post["text"]):
                    summary_tokens.append(token)
                    yield sse("stream_token", {"step": 6, "type": "summary", "token": token})
            except Exception:
                try:
                    summary, topics = await rag.summarize(post["text"])
                except Exception:
                    summary = post["text"][:500]
                    topics = []
                yield sse("step_complete", {"step": 6, "duration_ms": ms(), "summary": summary, "topics": topics})
            else:
                raw = "".join(summary_tokens)
                try:
                    s, e = raw.find("{"), raw.rfind("}")
                    data = _json.loads(raw[s:e+1])
                    summary = data.get("summary", "").strip()
                    topics = list(data.get("topics", []))
                except (ValueError, _json.JSONDecodeError):
                    summary = raw.strip()
                    topics = []
                yield sse("step_complete", {"step": 6, "duration_ms": ms(), "summary": summary, "topics": topics})

            # Step 7: Index
            yield sse("step_start", {"step": 7, "total_steps": 7, "name": "Indexing to Vector DB", "description": "Creating embeddings and storing in Qdrant..."})
            chunks = chunking.chunk_text(post["text"])
            vectors = []
            for i, chunk in enumerate(chunks):
                try:
                    vec = await embeddings.embed_text(chunk)
                except Exception as exc:  # noqa: BLE001
                    yield sse("step_fail", {"step": 7, "error": f"Embedding failed on chunk {i + 1}/{len(chunks)} ({type(exc).__name__})"})
                    return
                vectors.append(vec)
                yield sse("step_progress", {"step": 7, "progress": int(((i+1)/len(chunks))*100), "sub_text": f"Chunk {i+1}/{len(chunks)}"})

            vectorstore.ensure_collection()
            payloads = [{"text": c, "source_id": shortcode, "source_type": "instagram", "title": post["title"], "chunk_index": i, "channel": post.get("owner"), "thumbnail": post.get("thumbnail"), "url": payload.url} for i, c in enumerate(chunks)]
            try:
                vectorstore.delete_by_source_id(shortcode)
            except Exception as exc:  # noqa: BLE001
                logger.warning("delete_by_source_id failed for %s: %s", shortcode, exc)
            indexed = vectorstore.upsert_chunks(vectors, payloads)

            try:
                triples = await graph.extract_relations(post["text"])
                graph.add_triples(triples, shortcode, "instagram", post["title"])
            except Exception:
                pass

            yield sse("step_complete", {"step": 7, "duration_ms": ms()})

            item = SourceItem(source_id=shortcode, source_type="instagram", title=post["title"], channel=post["owner"], thumbnail=post["thumbnail"], summary=summary, key_topics=topics, chunks_indexed=indexed, url=payload.url)
            store.add_source(item)
            yield sse("complete", {"source_id": shortcode, "title": post["title"], "summary": summary, "key_topics": topics, "chunks_indexed": indexed})
        except Exception as exc:
            logger.exception("Instagram stream failed")
            yield sse("step_fail", {"step": 0, "error": public_error(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
