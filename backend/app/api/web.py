"""Web page ingestion endpoint."""
import hashlib
import json as _json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.models.schemas import SourceItem
from app.services import chunking, embeddings, graph, rag, store, vectorstore, web
from app.services.sse import public_error, sse

logger = get_logger(__name__)
router = APIRouter(prefix="/web", tags=["web"])

MIN_CONTENT_LENGTH = 50


class WebRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="Web page / article URL")


@router.post("/process", response_model=SourceItem)
async def process_web(payload: WebRequest) -> SourceItem:
    from app.services.commerce import reserve
    reserve("web")
    if web._is_youtube_video(payload.url):
        raise HTTPException(
            status_code=400,
            detail="This is a YouTube video — use the YouTube tab to ingest it (real transcripts, better summaries).",
        )
    try:
        article = await web.fetch_article(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch page") from exc
    if not article["text"] or len(article["text"].strip()) < MIN_CONTENT_LENGTH:
        raise HTTPException(status_code=422, detail="No readable content found or content too short")
    source_id = hashlib.sha1(web._normalize_url(payload.url).encode()).hexdigest()[:16]
    from app.services import ingest
    return await ingest.ingest_text(text=article["text"], source_id=source_id, source_type="web", title=article["title"], channel=payload.url, url=payload.url)


@router.post("/process/stream")
async def process_web_stream(payload: WebRequest):
    from app.services.commerce import reserve
    reserve("web")
    async def event_generator():
        t0 = time.time()
        def ms(): return round((time.time() - t0) * 1000)

        summary = ""
        topics: list[str] = []

        try:
            # Step 1: Validate
            yield sse("step_start", {"step": 1, "total_steps": 5, "name": "Validating URL", "description": "Checking if the URL is accessible..."})
            if not payload.url.startswith(("http://", "https://")):
                yield sse("step_fail", {"step": 1, "error": "URL must start with http:// or https://"})
                return
            if len(payload.url) > 2048:
                yield sse("step_fail", {"step": 1, "error": "URL is too long (max 2048 characters)"})
                return
            if web._is_youtube_video(payload.url):
                yield sse("step_fail", {"step": 1, "error": "This is a YouTube video — use the YouTube tab to ingest it (real transcripts, better summaries)."})
                return
            yield sse("step_complete", {"step": 1, "duration_ms": ms()})

            # Step 2: Fetch & Extract (Crawl4AI handles both)
            yield sse("step_start", {"step": 2, "total_steps": 5, "name": "Fetching & Extracting", "description": "Crawling page with Crawl4AI (JS rendering, content extraction)..."})
            try:
                article = await web.fetch_article(payload.url)
            except ValueError as exc:
                yield sse("step_fail", {"step": 2, "error": str(exc)})
                return
            except Exception as exc:
                logger.exception("Fetch failed for %s", payload.url)
                yield sse("step_fail", {"step": 2, "error": public_error(exc, "Content fetch")})
                return

            text = article.get("text", "").strip()
            if not text:
                yield sse("step_fail", {"step": 2, "error": "No readable content found on this page. The page may require JavaScript rendering or have anti-bot protection."})
                return

            if len(text) < MIN_CONTENT_LENGTH:
                yield sse("step_fail", {"step": 2, "error": f"Content too short ({len(text)} chars). The page may not have readable text content."})
                return

            title = article.get("title", payload.url)
            yield sse("step_complete", {"step": 2, "duration_ms": ms(), "title": title, "chars": len(text)})

            # Send preview content
            preview_text = text[:500] if len(text) > 500 else text
            yield sse("preview", {"type": "transcript", "text": preview_text, "chars": len(text), "title": title})

            # Step 3: Summary
            yield sse("step_start", {"step": 3, "total_steps": 5, "name": "Generating Summary", "description": "AI summarizing content using Ollama..."})
            summary_tokens = []
            try:
                async for token in rag.summarize_stream(text):
                    summary_tokens.append(token)
                    yield sse("stream_token", {"step": 3, "type": "summary", "token": token})
            except Exception:
                try:
                    summary, topics = await rag.summarize(text)
                except Exception:
                    # Use first 500 chars as summary fallback
                    summary = text[:500]
                    topics = []
                yield sse("step_complete", {"step": 3, "duration_ms": ms(), "summary": summary, "topics": topics})
            else:
                raw = "".join(summary_tokens)
                try:
                    s, e = raw.find("{"), raw.rfind("}")
                    data_j = _json.loads(raw[s:e+1])
                    summary = data_j.get("summary", "").strip()
                    topics = list(data_j.get("topics", []))
                except (ValueError, _json.JSONDecodeError):
                    summary = raw.strip()
                    topics = []
                yield sse("step_complete", {"step": 3, "duration_ms": ms(), "summary": summary, "topics": topics})

            # Step 4: Embeddings
            yield sse("step_start", {"step": 4, "total_steps": 5, "name": "Creating Embeddings", "description": "Generating vector embeddings..."})
            chunks = chunking.chunk_text(text)
            if not chunks:
                yield sse("step_fail", {"step": 4, "error": "No chunks generated from content"})
                return
            vectors = []
            for i, chunk in enumerate(chunks):
                try:
                    vec = await embeddings.embed_text(chunk)
                except Exception as exc:  # noqa: BLE001
                    yield sse("step_fail", {"step": 4, "error": f"Embedding failed on chunk {i + 1}/{len(chunks)} ({type(exc).__name__})"})
                    return
                vectors.append(vec)
                yield sse("step_progress", {"step": 4, "progress": int(((i+1)/len(chunks))*100), "sub_text": f"Chunk {i+1}/{len(chunks)}"})
            yield sse("step_complete", {"step": 4, "duration_ms": ms(), "vectors_count": len(vectors), "chunk_count": len(chunks)})

            # Step 5: Index
            yield sse("step_start", {"step": 5, "total_steps": 5, "name": "Indexing to Vector DB", "description": "Storing in Qdrant..."})
            source_id = hashlib.sha1(web._normalize_url(payload.url).encode()).hexdigest()[:16]
            payloads = [{"text": c, "source_id": source_id, "source_type": "web", "title": title, "chunk_index": i, "channel": payload.url, "url": payload.url} for i, c in enumerate(chunks)]
            vectorstore.ensure_collection()
            try:
                vectorstore.delete_by_source_id(source_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("delete_by_source_id failed for %s: %s", source_id, exc)
            indexed = vectorstore.upsert_chunks(vectors, payloads)
            try:
                triples = await graph.extract_relations(text)
                graph.add_triples(triples, source_id, "web", title)
            except Exception:
                pass
            item = SourceItem(source_id=source_id, source_type="web", title=title, channel=payload.url, summary=summary, key_topics=topics, chunks_indexed=indexed, url=payload.url)
            store.add_source(item)
            yield sse("step_complete", {"step": 5, "duration_ms": ms()})
            yield sse("complete", {"source_id": source_id, "title": title, "summary": summary, "key_topics": topics, "chunks_indexed": indexed})
        except Exception as exc:
            logger.exception("Web stream failed")
            yield sse("step_fail", {"step": 0, "error": public_error(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
