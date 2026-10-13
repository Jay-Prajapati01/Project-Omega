"""PDF ingestion endpoint with 13-step Docling pipeline (multipart upload)."""
import hashlib
import json as _json
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.uploads import read_upload
from app.models.schemas import SourceItem
from app.services import embeddings, graph, rag, store, vectorstore
from app.services.pdf_validator import validate as validate_pdf
from app.services.pdf_chunker import chunk_document
from app.services.sse import public_error, sse

logger = get_logger(__name__)
router = APIRouter(prefix="/pdf", tags=["pdf"])

TOTAL_STEPS = 13


def _get_extract_document():
    """Lazy import of extract_document with fallback."""
    try:
        from app.services.pdf_pipeline import extract_document
        return extract_document
    except ImportError:
        logger.warning("Docling not available, using PyMuPDF fallback")
        from app.services.pdf import _fallback_extract_text

        class _FallbackDoc:
            def __init__(self, data, filename):
                result = _fallback_extract_text(data, filename)
                self.title = result.get("title", filename)
                self.markdown = result.get("text", "")
                self.page_count = result.get("pages", 0)
                self.headings = []
                self.sections = []
                self.tables = []
                self.images = []
                self.paragraphs = []
                self.captions = []
                self.metadata = {}
                self.document_type = "unknown"
                self.needs_ocr = False

        def fallback_extract(data, filename):
            return _FallbackDoc(data, filename)

        return fallback_extract


@router.post("/process", response_model=SourceItem)
async def process_pdf(file: UploadFile = File(...)) -> SourceItem:
    from app.services.commerce import reserve
    reserve("pdf")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a .pdf file")
    data = await read_upload(file, get_settings().pdf_max_file_size)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    validation = validate_pdf(data, file.filename)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.errors[0])

    extract_doc = _get_extract_document()
    try:
        doc = extract_doc(data, file.filename)
    except Exception as exc:
        logger.exception("PDF parsing failed")
        raise HTTPException(status_code=422, detail="Failed to parse PDF") from exc

    if not doc.markdown:
        raise HTTPException(status_code=422, detail="No extractable text in PDF")

    source_id = hashlib.sha1(data).hexdigest()[:16]
    from app.services import file_storage, ingest
    file_path = file_storage.save_file(source_id, data, "pdf", file.filename)
    return await ingest.ingest_text(text=doc.markdown, source_id=source_id, source_type="pdf", title=doc.title, file_path=file_path, file_name=file.filename, file_size=len(data), mime_type="application/pdf", structured_chunks=chunk_document(doc.markdown, doc.sections), page_count=doc.page_count)


@router.post("/process/stream")
async def process_pdf_stream(file: UploadFile = File(...)):
    from app.services.commerce import reserve
    reserve("pdf")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a .pdf file")
    file_data = await read_upload(file, get_settings().pdf_max_file_size)
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
            # Step 1: Validate PDF
            yield sse("step_start", {"step": 1, "total_steps": TOTAL_STEPS, "name": "Validating PDF", "description": "Checking format, size, and encryption..."})
            validation = validate_pdf(file_data, file_name)
            if not validation.valid:
                yield sse("step_fail", {"step": 1, "error": validation.errors[0]})
                return
            source_id = hashlib.sha1(file_data).hexdigest()[:16]
            yield sse("step_complete", {"step": 1, "duration_ms": ms(), "filename": file_name, "size_kb": len(file_data) // 1024, "warnings": validation.warnings})

            # Save original file to disk
            from app.services import file_storage
            file_path = file_storage.save_file(source_id, file_data, "pdf", file_name)
            # file_path returned is like "files/pdf/abc123.pdf"

            # Step 2: Detect Document Type
            yield sse("step_start", {"step": 2, "total_steps": TOTAL_STEPS, "name": "Detecting Document Type", "description": "Analyzing document structure and metadata..."})
            yield sse("step_complete", {"step": 2, "duration_ms": ms(), "needs_ocr": validation.needs_ocr, "page_count": validation.page_count})

            # Step 3: Parse Layout (Docling)
            yield sse("step_start", {"step": 3, "total_steps": TOTAL_STEPS, "name": "Parsing Layout", "description": "Extracting structure using Docling document intelligence..."})
            extract_doc = _get_extract_document()
            try:
                doc = extract_doc(file_data, file_name)
            except Exception as exc:
                logger.exception("PDF layout extraction failed")
                yield sse("step_fail", {"step": 3, "error": public_error(exc, "PDF parsing")})
                return
            if not doc.markdown:
                yield sse("step_fail", {"step": 3, "error": "No extractable text in PDF"})
                return
            yield sse("step_complete", {"step": 3, "duration_ms": ms(), "title": doc.title, "chars": len(doc.markdown), "headings_count": len(doc.headings), "sections_count": len(doc.sections)})

            # Step 4: Running OCR (conditional)
            yield sse("step_start", {"step": 4, "total_steps": TOTAL_STEPS, "name": "Running OCR", "description": "Tesseract OCR processing scanned pages..."})
            if validation.needs_ocr:
                yield sse("step_progress", {"step": 4, "progress": 50, "sub_text": f"OCR applied to {validation.scanned_page_count} pages"})
                yield sse("step_complete", {"step": 4, "duration_ms": ms(), "ocr_pages": validation.scanned_page_count})
            else:
                yield sse("step_progress", {"step": 4, "progress": 100, "sub_text": "No OCR needed - all pages have extractable text"})
                yield sse("step_complete", {"step": 4, "duration_ms": ms(), "ocr_pages": 0})

            # Step 5: Extract Tables
            yield sse("step_start", {"step": 5, "total_steps": TOTAL_STEPS, "name": "Extracting Tables", "description": "Detecting and extracting table structures..."})
            tables = doc.tables
            yield sse("step_complete", {"step": 5, "duration_ms": ms(), "tables_count": len(tables)})

            # Step 6: Extract Images
            yield sse("step_start", {"step": 6, "total_steps": TOTAL_STEPS, "name": "Extracting Images", "description": "Identifying images and figures..."})
            images = doc.images
            yield sse("step_complete", {"step": 6, "duration_ms": ms(), "images_count": len(images)})

            # Step 7: Detect Headings
            yield sse("step_start", {"step": 7, "total_steps": TOTAL_STEPS, "name": "Detecting Headings", "description": "Building document hierarchy..."})
            headings = doc.headings
            yield sse("step_complete", {"step": 7, "duration_ms": ms(), "headings": headings[:10]})

            # Step 8: Create Structured Content
            yield sse("step_start", {"step": 8, "total_steps": TOTAL_STEPS, "name": "Creating Structured Content", "description": "Assembling markdown representation..."})
            yield sse("step_complete", {"step": 8, "duration_ms": ms(), "document_type": doc.document_type})

            # Step 9: Clean Document
            yield sse("step_start", {"step": 9, "total_steps": TOTAL_STEPS, "name": "Cleaning Document", "description": "Normalizing text and fixing artifacts..."})
            text = doc.markdown
            yield sse("step_complete", {"step": 9, "duration_ms": ms(), "final_chars": len(text)})

            # Emit document structure preview
            yield sse("document_structure", {
                "title": doc.title,
                "headings_count": len(headings),
                "tables_count": len(tables),
                "images_count": len(images),
                "sections_count": len(doc.sections),
                "document_type": doc.document_type,
            })

            # Step 10: Semantic Chunking
            yield sse("step_start", {"step": 10, "total_steps": TOTAL_STEPS, "name": "Semantic Chunking", "description": "Splitting by headings and sentences..."})
            chunks = chunk_document(text, sections=doc.sections)
            if not chunks:
                yield sse("step_fail", {"step": 10, "error": "No indexable text content"})
                return
            yield sse("step_complete", {"step": 10, "duration_ms": ms(), "chunk_count": len(chunks)})

            # Step 11: Creating Embeddings
            yield sse("step_start", {"step": 11, "total_steps": TOTAL_STEPS, "name": "Creating Embeddings", "description": "Generating vector embeddings..."})
            chunk_texts = [c["text"] for c in chunks]
            vectors = []
            for i, chunk_text in enumerate(chunk_texts):
                try:
                    vec = await embeddings.embed_text(chunk_text)
                except Exception as exc:  # noqa: BLE001
                    yield sse("step_fail", {"step": 11, "error": f"Embedding failed on chunk {i + 1}/{len(chunk_texts)} ({type(exc).__name__})"})
                    return
                vectors.append(vec)
                yield sse("step_progress", {"step": 11, "progress": int(((i + 1) / len(chunk_texts)) * 100), "sub_text": f"Chunk {i + 1}/{len(chunk_texts)}"})
            yield sse("step_complete", {"step": 11, "duration_ms": ms(), "vectors_count": len(vectors)})

            # Step 12: Summary generation
            yield sse("step_start", {"step": 12, "total_steps": TOTAL_STEPS, "name": "Generating Summary", "description": "AI summarizing content using Ollama..."})
            summary_tokens = []
            try:
                async for token in rag.summarize_stream(text):
                    summary_tokens.append(token)
                    yield sse("stream_token", {"step": 12, "type": "summary", "token": token})
            except Exception:
                try:
                    summary, topics = await rag.summarize(text)
                except Exception:
                    summary = text[:500]
                    topics = []
            else:
                raw = "".join(summary_tokens)
                try:
                    s, e = raw.find("{"), raw.rfind("}")
                    data_j = _json.loads(raw[s:e + 1])
                    summary = data_j.get("summary", "").strip()
                    topics = list(data_j.get("topics", []))
                except (ValueError, _json.JSONDecodeError):
                    summary = raw.strip()
                    topics = []
            yield sse("step_complete", {"step": 12, "duration_ms": ms(), "summary": summary, "topics": topics})

            # Step 13: Indexing to Vector DB
            yield sse("step_start", {"step": 13, "total_steps": TOTAL_STEPS, "name": "Indexing to Vector DB", "description": "Storing in Qdrant and building knowledge graph..."})
            payloads = [
                {
                    "text": c["text"],
                    "source_id": source_id,
                    "source_type": "pdf",
                    "title": doc.title,
                    "chunk_index": c["chunk_index"],
                    "section_heading": c.get("section_heading", ""),
                    "file_path": file_path,  # Use the path returned by save_file
                    "file_name": file_name,
                }
                for c in chunks
            ]
            vectorstore.ensure_collection()
            try:
                vectorstore.delete_by_source_id(source_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("delete_by_source_id failed for %s: %s", source_id, exc)
            indexed = vectorstore.upsert_chunks(vectors, payloads)
            try:
                triples = await graph.extract_relations(text)
                graph.add_triples(triples, source_id, "pdf", doc.title)
            except Exception:
                pass
            yield sse("step_complete", {"step": 13, "duration_ms": ms()})

            item = SourceItem(source_id=source_id, source_type="pdf", title=doc.title, summary=summary, key_topics=topics, chunks_indexed=indexed, file_path=file_path, file_name=file_name, file_size=len(file_data), mime_type="application/pdf", page_count=validation.page_count)
            store.add_source(item)
            completed = True
            yield sse("complete", {"source_id": source_id, "title": doc.title, "summary": summary, "key_topics": topics, "chunks_indexed": indexed})
        except Exception as exc:
            logger.exception("PDF stream failed")
            yield sse("step_fail", {"step": 0, "error": public_error(exc)})
        finally:
            if not completed and file_path and source_id:
                from app.services import file_storage
                if file_storage.cleanup_if_unreferenced(file_path, source_id):
                    logger.info("Removed unreferenced upload after failed PDF pipeline: %s", file_path)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
