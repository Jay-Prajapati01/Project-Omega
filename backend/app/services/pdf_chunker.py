"""Heading-aware semantic chunking for PDF documents.

Splits documents by headings first, then sentence-aware splitting within
sections. Each chunk carries metadata for better retrieval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.chunking import _hard_split

logger = get_logger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class ChunkMetadata:
    text: str
    section_heading: str = ""
    page_number: int = 0
    chunk_index: int = 0


def chunk_document(
    markdown: str,
    sections: list[dict] | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    """Chunk a document using heading-aware splitting.

    First splits by headings, then applies sentence-aware splitting
    within each section. Returns chunks with rich metadata.
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    if not markdown or not markdown.strip():
        return []

    # Split by headings
    heading_sections = _split_by_headings(markdown)

    chunks: list[dict] = []
    chunk_idx = 0

    for section in heading_sections:
        heading = section["heading"]
        text = section["text"].strip()

        if not text:
            continue

        # Sentence-aware splitting within section
        section_chunks = _split_sentences(text, chunk_size, overlap)

        for chunk_text in section_chunks:
            chunks.append({
                "text": chunk_text,
                "section_heading": heading,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    return chunks


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Legacy interface: flat sentence-aware chunking (no heading awareness).

    Kept for backward compatibility with non-PDF sources.
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []

    return _split_sentences(text, chunk_size, overlap)


def _split_by_headings(markdown: str) -> list[dict]:
    """Split markdown into sections by headings."""
    lines = markdown.split("\n")
    sections: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            # Save previous section
            if current_lines or current_heading:
                sections.append({
                    "heading": current_heading,
                    "text": "\n".join(current_lines),
                })
            current_heading = heading_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_lines or current_heading:
        sections.append({
            "heading": current_heading,
            "text": "\n".join(current_lines),
        })

    return sections


def _split_sentences(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks respecting sentence boundaries.

    Guarantees every chunk is <= chunk_size: pieces without sentence
    punctuation (markdown tables, CSV rows) are hard-split on word
    boundaries, otherwise one giant line becomes an oversized chunk that
    the embedding API rejects.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    max_piece = max(chunk_size - overlap - 1, chunk_size // 2)
    pieces: list[str] = []
    for sentence in _SENTENCE_RE.split(text):
        pieces.extend(_hard_split(sentence, max_piece))

    chunks: list[str] = []
    current = ""

    for sentence in pieces:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if overlap and current else ""
            current = f"{tail} {sentence}".strip()

    if current:
        chunks.append(current)

    return chunks
