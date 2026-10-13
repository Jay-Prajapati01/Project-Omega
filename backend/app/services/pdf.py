"""PDF ingestion: Docling-based document intelligence with Tesseract OCR.

This module provides the public interface for PDF text extraction.
It delegates to the pdf_pipeline for structured extraction and falls
back to PyMuPDF if Docling is unavailable.
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text(data: bytes, filename: str) -> dict:
    """Extract text from PDF bytes (legacy interface).

    Returns a dict with keys: title, text, pages.
    For structured extraction, use extract_document() instead.
    """
    try:
        from app.services.pdf_pipeline import extract_document
        doc = extract_document(data, filename)
        return {
            "title": (doc.title or filename).strip(),
            "text": doc.markdown,
            "pages": doc.page_count,
        }
    except ImportError:
        logger.warning("Docling not available, falling back to PyMuPDF")
        return _fallback_extract_text(data, filename)
    except Exception as exc:
        logger.warning("Docling extraction failed, falling back to PyMuPDF: %s", exc)
        return _fallback_extract_text(data, filename)


def extract_document(data: bytes, filename: str):
    """Extract structured document from PDF bytes.

    Returns a PDFDocument with full structure: headings, tables,
    images, sections, and markdown representation.
    """
    from app.services.pdf_pipeline import extract_document as _extract
    return _extract(data, filename)


def _fallback_extract_text(data: bytes, filename: str) -> dict:
    """Fallback to PyMuPDF if Docling is unavailable."""
    import fitz  # PyMuPDF

    _MIN_TEXT_PER_PAGE = 40

    def _ocr_page(page) -> str:
        try:
            import io
            import pytesseract
            from PIL import Image

            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            return pytesseract.image_to_string(img).strip()
        except Exception as exc:
            logger.warning("OCR failed on page %s: %s", page.number, exc)
            return ""

    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if len(text) < _MIN_TEXT_PER_PAGE:
            ocr = _ocr_page(page)
            if len(ocr) > len(text):
                text = ocr
        if text:
            parts.append(text)

    title = doc.metadata.get("title") if doc.metadata else None
    pages = doc.page_count
    doc.close()

    return {
        "title": (title or filename).strip(),
        "text": "\n\n".join(parts).strip(),
        "pages": pages,
    }
