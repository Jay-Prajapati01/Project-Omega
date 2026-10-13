"""PDF validation: format, size, encryption, and OCR necessity detection."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_PDF_MAGIC = b"%PDF"
_MIN_TEXT_PER_PAGE = 40
_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@dataclass
class ValidationResult:
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    is_encrypted: bool = False
    needs_ocr: bool = False
    page_count: int = 0
    scanned_page_count: int = 0


def validate(data: bytes, filename: str = "") -> ValidationResult:
    """Validate PDF bytes and detect processing requirements.

    Returns a ValidationResult with validity status, warnings, and
    whether OCR will likely be needed.
    """
    result = ValidationResult()

    if not data:
        result.valid = False
        result.errors.append("Empty file")
        return result

    if len(data) < 4:
        result.valid = False
        result.errors.append("File too small to be a valid PDF")
        return result

    if not data[:4] == _PDF_MAGIC:
        result.valid = False
        result.errors.append("Not a valid PDF file (missing %PDF header)")
        return result

    if len(data) > _MAX_FILE_SIZE:
        result.valid = False
        result.errors.append(f"File exceeds maximum size of {_MAX_FILE_SIZE // (1024 * 1024)} MB")
        return result

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        result.page_count = doc.page_count

        # Page count cap to prevent resource exhaustion (M-10)
        settings = get_settings()
        if settings.max_pdf_pages and result.page_count > settings.max_pdf_pages:
            result.valid = False
            result.errors.append(
                f"PDF has {result.page_count} pages, exceeding the limit of "
                f"{settings.max_pdf_pages} pages"
            )
            doc.close()
            return result

        if doc.is_encrypted:
            result.is_encrypted = True
            result.warnings.append("PDF is encrypted; some content may not be accessible")

        scanned_pages = 0
        for page in doc:
            text = page.get_text().strip()
            if len(text) < _MIN_TEXT_PER_PAGE:
                scanned_pages += 1

        result.scanned_page_count = scanned_pages
        if scanned_pages > 0:
            result.needs_ocr = True
            ratio = scanned_pages / max(doc.page_count, 1)
            if ratio > 0.5:
                result.warnings.append(
                    f"{scanned_pages}/{doc.page_count} pages appear scanned; OCR will be used"
                )
            else:
                result.warnings.append(
                    f"{scanned_pages}/{doc.page_count} pages have limited text; OCR may be used for those pages"
                )

        doc.close()
    except Exception as exc:
        logger.warning("PDF validation scan failed: %s", exc)
        result.warnings.append("Could not fully analyze PDF structure")

    return result
