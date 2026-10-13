"""PDF metadata extraction: title, author, dates, language, document type."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

_DOCUMENT_TYPE_PATTERNS: dict[str, list[str]] = {
    "research_paper": [r"abstract", r"introduction", r"methodology", r"conclusion", r"references", r"doi:"],
    "invoice": [r"invoice", r"bill to", r"total amount", r"payment due", r"tax id"],
    "report": [r"executive summary", r"findings", r"recommendations", r"quarterly", r"annual"],
    "resume": [r"experience", r"education", r"skills", r"objective", r"references available"],
    "manual": [r"table of contents", r"chapter", r"section \d", r"appendix", r"glossary"],
    "legal": [r"whereas", r"hereinafter", r"party", r"agreement", r"terms and conditions"],
}


@dataclass
class PDFMetadata:
    title: str = ""
    author: str | None = None
    creation_date: str | None = None
    page_count: int = 0
    language: str | None = None
    file_size: int = 0
    document_type: str = "unknown"
    metadata: dict = field(default_factory=dict)


def extract_metadata(data: bytes, filename: str) -> PDFMetadata:
    """Extract metadata from PDF bytes.

    Returns a PDFMetadata object with title, author, dates, and
    detected document type.
    """
    meta = PDFMetadata(file_size=len(data))
    meta.title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title() if filename else "Untitled"

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        meta.page_count = doc.page_count

        info = doc.metadata or {}
        if info.get("title"):
            meta.title = info["title"].strip() or meta.title
        if info.get("author"):
            meta.author = info["author"].strip() or None
        if info.get("creationDate"):
            meta.creation_date = info["creationDate"]
        if info.get("subject"):
            meta.language = _detect_language_from_subject(info["subject"])

        meta.metadata = {
            "title": info.get("title", ""),
            "author": info.get("author", ""),
            "subject": info.get("subject", ""),
            "keywords": info.get("keywords", ""),
            "creator": info.get("creator", ""),
            "producer": info.get("producer", ""),
            "creation_date": info.get("creationDate", ""),
            "mod_date": info.get("modDate", ""),
        }

        sample_text = _extract_sample_text(doc)
        meta.document_type = _detect_document_type(sample_text)

        doc.close()
    except Exception as exc:
        logger.warning("Metadata extraction failed: %s", exc)

    return meta


def _extract_sample_text(doc, max_pages: int = 5) -> str:
    """Extract text from first few pages for document type detection."""
    parts: list[str] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        parts.append(page.get_text()[:2000])
    return "\n".join(parts)


def _detect_document_type(text: str) -> str:
    """Heuristic detection of document type from content patterns."""
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for doc_type, patterns in _DOCUMENT_TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, text_lower))
        if score > 0:
            scores[doc_type] = score

    if scores:
        return max(scores, key=scores.get)
    return "document"


def _detect_language_from_subject(subject: str) -> str | None:
    """Try to detect language from PDF subject field."""
    subject_lower = subject.lower()
    lang_map = {
        "english": "en", "french": "fr", "german": "de", "spanish": "es",
        "italian": "it", "portuguese": "pt", "chinese": "zh", "japanese": "ja",
        "korean": "ko", "arabic": "ar", "russian": "ru", "hindi": "hi",
    }
    for lang_name, code in lang_map.items():
        if lang_name in subject_lower:
            return code
    return None
