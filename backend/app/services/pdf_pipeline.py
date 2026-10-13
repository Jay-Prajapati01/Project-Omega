"""PDF pipeline: Docling-based document intelligence with Tesseract OCR.

This is the core extraction engine that converts PDF bytes into structured
documents with headings, tables, images, and markdown representation.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Lazy-loaded converter singleton
_converter = None


@dataclass
class PDFDocument:
    """Structured output from PDF pipeline."""
    title: str = ""
    author: str | None = None
    creation_date: str | None = None
    page_count: int = 0
    language: str | None = None
    file_size: int = 0
    document_type: str = "unknown"
    headings: list[str] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    markdown: str = ""
    chunks: list[dict] = field(default_factory=list)
    needs_ocr: bool = False


def _get_converter():
    """Lazy-initialize the Docling converter with Tesseract OCR backend."""
    global _converter
    if _converter is not None:
        return _converter

    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        if os.environ.get("DOCLING_ARTIFACTS_PATH"):
            from pathlib import Path
            pipeline_options.artifacts_path = Path(os.environ["DOCLING_ARTIFACTS_PATH"])
        pipeline_options.do_table_structure = True
        pipeline_options.do_ocr = True

        from docling.datamodel.pipeline_options import TesseractCliOcrOptions
        pipeline_options.ocr_options = TesseractCliOcrOptions()

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        logger.info("Docling converter initialized successfully")
    except ImportError as exc:
        logger.error("Docling not installed: %s", exc)
        raise ImportError(
            "Docling is required for PDF processing. "
            "Install with: pip install docling"
            " (requires the tesseract-ocr system package)"
        ) from exc

    return _converter


def extract_document(data: bytes, filename: str) -> PDFDocument:
    """Extract structured document from PDF bytes using Docling.

    Returns a PDFDocument with full structure: headings, tables,
    images, sections, and markdown representation.
    """
    from app.services.pdf_metadata import extract_metadata
    from app.services.pdf_cleaner import clean_markdown

    # Extract metadata first
    meta = extract_metadata(data, filename)

    doc = PDFDocument(
        title=meta.title,
        author=meta.author,
        creation_date=meta.creation_date,
        page_count=meta.page_count,
        language=meta.language,
        file_size=meta.file_size,
        document_type=meta.document_type,
        metadata=meta.metadata,
    )

    # Write to temp file for Docling (it needs a file path)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        converter = _get_converter()
        result = converter.convert(tmp_path)
        dl_doc = result.document

        # Extract structured content from Docling document
        doc.markdown = _extract_markdown(dl_doc)
        doc.headings = _extract_headings(dl_doc)
        doc.sections = _extract_sections(dl_doc)
        doc.tables = _extract_tables(dl_doc)
        doc.images = _extract_images(dl_doc)
        doc.paragraphs = _extract_paragraphs(dl_doc)
        doc.captions = _extract_captions(dl_doc)

        # Clean the markdown
        doc.markdown = clean_markdown(doc.markdown)

    except ImportError:
        raise
    except Exception as exc:
        logger.warning("Docling extraction failed, falling back to PyMuPDF: %s", exc)
        doc = _fallback_extract(data, filename, doc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return doc


def _extract_markdown(dl_doc) -> str:
    """Extract markdown representation from Docling document."""
    try:
        return dl_doc.export_to_markdown()
    except Exception:
        return ""


PARAGRAPH_LABELS = ("paragraph", "text", "list_item")
SECTION_LABELS = ("section_header", "title", "subtitle")


def _label_of(item) -> str:
    """Normalize DocItemLabel enum / string labels to a plain string."""
    label = getattr(item, "label", None)
    return str(getattr(label, "value", label) or "")


def _extract_headings(dl_doc) -> list[str]:
    """Extract heading texts from Docling document."""
    headings: list[str] = []
    try:
        for item in dl_doc.texts:
            if _label_of(item) in SECTION_LABELS:
                text = getattr(item, "text", "") or ""
                if text.strip():
                    headings.append(text.strip())
    except Exception:
        pass
    return headings


def _extract_sections(dl_doc) -> list[dict]:
    """Extract sections with headings and content."""
    sections: list[dict] = []
    current_heading = ""
    current_text: list[str] = []

    try:
        for item in dl_doc.texts:
            label = _label_of(item)
            if label in SECTION_LABELS:
                # Save previous section
                if current_text:
                    sections.append({
                        "heading": current_heading,
                        "text": "\n".join(current_text),
                    })
                current_heading = getattr(item, "text", "") or ""
                current_text = []
            elif label in PARAGRAPH_LABELS:
                text = getattr(item, "text", "") or ""
                if text.strip():
                    current_text.append(text.strip())

        # Save last section
        if current_text:
            sections.append({
                "heading": current_heading,
                "text": "\n".join(current_text),
            })
    except Exception:
        pass

    return sections


def _extract_tables(dl_doc) -> list[dict]:
    """Extract tables as markdown representation."""
    tables: list[dict] = []
    try:
        for table in dl_doc.tables:
            try:
                try:
                    md = table.export_to_markdown(doc=dl_doc)
                except TypeError:
                    md = table.export_to_markdown()
                if md and md.strip():
                    caption = ""
                    cap_obj = getattr(table, "caption", None)
                    if cap_obj:
                        caption = (getattr(cap_obj, "text", "") or "").strip()
                    tables.append({"content": md.strip(), "caption": caption})
            except Exception:
                pass
    except Exception:
        pass
    return tables


def _extract_images(dl_doc) -> list[dict]:
    """Extract image references and captions."""
    images: list[dict] = []
    try:
        for item in dl_doc.pictures:
            caption = ""
            if hasattr(item, "caption") and item.caption:
                caption = getattr(item.caption, "text", "") or ""
            images.append({"caption": caption.strip()})
    except Exception:
        pass
    return images


def _extract_paragraphs(dl_doc) -> list[str]:
    """Extract paragraph texts."""
    paragraphs: list[str] = []
    try:
        for item in dl_doc.texts:
            if _label_of(item) in PARAGRAPH_LABELS:
                text = getattr(item, "text", "") or ""
                if text.strip():
                    paragraphs.append(text.strip())
    except Exception:
        pass
    return paragraphs


def _extract_captions(dl_doc) -> list[str]:
    """Extract figure/table captions."""
    captions: list[str] = []
    try:
        for item in dl_doc.texts:
            if _label_of(item) in ("caption", "table_caption", "figure_caption"):
                text = getattr(item, "text", "") or ""
                if text.strip():
                    captions.append(text.strip())
    except Exception:
        pass
    return captions


def _fallback_extract(data: bytes, filename: str, doc: PDFDocument) -> PDFDocument:
    """Fallback to PyMuPDF if Docling fails."""
    try:
        import fitz  # PyMuPDF

        pdf_doc = fitz.open(stream=data, filetype="pdf")
        doc.page_count = pdf_doc.page_count

        parts: list[str] = []
        for page in pdf_doc:
            text = page.get_text().strip()
            if text:
                parts.append(text)

        doc.markdown = "\n\n".join(parts)
        doc.paragraphs = [p for p in doc.markdown.split("\n\n") if p.strip()]

        # Extract headings from text (ALL CAPS lines or numbered sections)
        import re
        for line in doc.markdown.split("\n"):
            line = line.strip()
            if re.match(r"^[A-Z][A-Z\s]{3,}$", line) or re.match(r"^\d+(\.\d+)*\s+[A-Z]", line):
                doc.headings.append(line)

        pdf_doc.close()
    except Exception as exc:
        logger.error("Fallback extraction also failed: %s", exc)
        doc.markdown = ""

    return doc
