"""Audio ingestion endpoint (multipart upload)."""
import hashlib
import json as _json
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.core.uploads import read_upload
from app.models.schemas import SourceItem
from app.services import audio, chunking, embeddings, graph, rag, store, vectorstore
from app.services.sse import public_error, sse

logger = get_logger(__name__)
router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/process", response_model=SourceItem)
async def process_audio(file: UploadFile = File(...)) -> SourceItem:
    from app.services.commerce import reserve
    reserve("audio")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    data = await read_upload(file)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        parsed = audio.transcribe(data, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Failed to transcribe audio") from exc
    if not parsed["text"]:
        raise HTTPException(status_code=422, detail="No speech detected")
    source_id = hashlib.sha1(data).hexdigest()[:16]
    from app.services import file_storage, ingest
    file_path = file_storage.save_file(source_id, data, "audio", file.filename)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg", "flac": "audio/flac", "aac": "audio/aac", "webm": "audio/webm"}
    return await ingest.ingest_text(text=parsed["text"], source_id=source_id, source_type="audio", title=parsed["title"], file_path=file_path, file_name=file.filename, file_size=len(data), mime_type=mime_map.get(ext, "application/octet-stream"))


@router.post("/process/stream")
async def process_audio_stream(file: UploadFile = File(...)):
    from app.services.commerce import reserve
    reserve("audio")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    file_data = await read_upload(file)
    if not file_data:
        raise HTTPException(status_code=400, detail="Empty file")
    file_name = file.filename

    async def event_generator():
        t0 = time.time()
        def ms(): return round((time.time() - t0) * 1000)

        summary = ""
        topics: list[str] = []
        file_path: str | None = None
        source_id: str | None = None
        completed = False

        try:
            # Step 1: Upload
            yield sse("step_start", {"step": 1, "total_steps": 6, "name": "Uploading File", "description": "Reading audio file into memory..."})
            data = file_data
            source_id = hashlib.sha1(data).hexdigest()[:16]
            yield sse("step_complete", {"step": 1, "duration_ms": ms(), "filename": file_name, "size_kb": len(data) // 1024})

            # Save original file to disk
            from app.services import file_storage
            file_path = file_storage.save_file(source_id, data, "audio", file_name)

            # Step 2: Transcribe
            yield sse("step_start", {"step": 2, "total_steps": 6, "name": "Transcribing Audio", "description": "Converting speech to text using Whisper..."})
            try:
                parsed = audio.transcribe(data, file_name)
            except ValueError as exc:
                yield sse("step_fail", {"step": 2, "error": str(exc)})
                return
            except Exception as exc:
                logger.exception("Audio transcription failed")
                yield sse("step_fail", {"step": 2, "error": public_error(exc, "Transcription")})
                return
            if not parsed["text"]:
                yield sse("step_fail", {"step": 2, "error": "No speech detected"})
                return
            yield sse("step_complete", {"step": 2, "duration_ms": ms(), "chars": len(parsed["text"]), "preview": parsed["text"][:300]})

            # Step 3: Summary
            yield sse("step_start", {"step": 3, "total_steps": 6, "name": "Generating Summary", "description": "AI summarizing content using Ollama..."})
            summary_tokens = []
            try:
                async for token in rag.summarize_stream(parsed["text"]):
                    summary_tokens.append(token)
                    yield sse("stream_token", {"step": 3, "type": "summary", "token": token})
            except Exception:
                try:
                    summary, topics = await rag.summarize(parsed["text"])
                except Exception:
                    summary = parsed["text"][:500]
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

            # Step 4: Chunk
            yield sse("step_start", {"step": 4, "total_steps": 6, "name": "Chunking Content", "description": "Splitting text into indexable chunks..."})
            chunks = chunking.chunk_text(parsed["text"])
            yield sse("step_complete", {"step": 4, "duration_ms": ms(), "chunk_count": len(chunks)})

            # Step 5: Embeddings
            yield sse("step_start", {"step": 5, "total_steps": 6, "name": "Creating Embeddings", "description": "Generating vector embeddings..."})
            vectors = []
            for i, chunk in enumerate(chunks):
                try:
                    vec = await embeddings.embed_text(chunk)
                except Exception as exc:  # noqa: BLE001
                    yield sse("step_fail", {"step": 5, "error": f"Embedding failed on chunk {i + 1}/{len(chunks)} ({type(exc).__name__})"})
                    return
                vectors.append(vec)
                yield sse("step_progress", {"step": 5, "progress": int(((i+1)/len(chunks))*100), "sub_text": f"Chunk {i+1}/{len(chunks)}"})
            yield sse("step_complete", {"step": 5, "duration_ms": ms(), "vectors_count": len(vectors)})

            # Step 6: Index
            yield sse("step_start", {"step": 6, "total_steps": 6, "name": "Indexing to Vector DB", "description": "Storing in Qdrant..."})
            payloads = [{"text": c, "source_id": source_id, "source_type": "audio", "title": parsed.get("title"), "chunk_index": i, "file_path": file_path, "file_name": file_name} for i, c in enumerate(chunks)]
            vectorstore.ensure_collection()
            try:
                vectorstore.delete_by_source_id(source_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("delete_by_source_id failed for %s: %s", source_id, exc)
            indexed = vectorstore.upsert_chunks(vectors, payloads)
            try:
                triples = await graph.extract_relations(parsed["text"])
                graph.add_triples(triples, source_id, "audio", parsed.get("title"))
            except Exception:
                pass
            yield sse("step_complete", {"step": 6, "duration_ms": ms()})

            ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
            mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg", "flac": "audio/flac", "aac": "audio/aac", "webm": "audio/webm"}
            item = SourceItem(source_id=source_id, source_type="audio", title=parsed.get("title"), summary=summary, key_topics=topics, chunks_indexed=indexed, file_path=file_path, file_name=file_name, file_size=len(data), mime_type=mime_map.get(ext, "application/octet-stream"))
            store.add_source(item)
            completed = True
            yield sse("complete", {"source_id": source_id, "title": parsed.get("title"), "summary": summary, "key_topics": topics, "chunks_indexed": indexed})
        except Exception as exc:
            logger.exception("Audio stream failed")
            yield sse("step_fail", {"step": 0, "error": public_error(exc)})
        finally:
            if not completed and file_path and source_id:
                from app.services import file_storage
                if file_storage.cleanup_if_unreferenced(file_path, source_id):
                    logger.info("Removed unreferenced upload after failed audio pipeline: %s", file_path)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
