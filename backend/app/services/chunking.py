"""Smart text chunking with sentence-aware splitting and overlap."""
from __future__ import annotations

import re

from app.core.config import get_settings

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _hard_split(piece: str, max_len: int) -> list[str]:
    """Split a piece that has no sentence boundaries into <= max_len parts.

    Tables, CSV rows and long URLs produce "sentences" with no .!? that can
    be far larger than chunk_size. Without this, one such line becomes a
    single oversized chunk and Ollama rejects it with 400
    "the input length exceeds the context length".
    """
    if len(piece) <= max_len:
        return [piece]

    out: list[str] = []
    current = ""
    for word in piece.split(" "):
        if len(word) > max_len:
            # single token (e.g. base64/minified data) longer than the limit
            if current:
                out.append(current)
                current = ""
            out.extend(word[i : i + max_len] for i in range(0, len(word), max_len))
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                out.append(current)
            current = word
    if current:
        out.append(current)
    return out


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks, respecting sentence boundaries.

    Every returned chunk is <= chunk_size characters, even when the input
    has no sentence punctuation at all (tables, CSV, minified JSON).
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []

    # Leave room for the overlap tail + joining space so a chunk can never
    # exceed chunk_size.
    max_piece = max(chunk_size - overlap - 1, chunk_size // 2)

    pieces: list[str] = []
    for sentence in _SENTENCE_RE.split(text):
        pieces.extend(_hard_split(sentence, max_piece))

    chunks: list[str] = []
    current = ""

    for piece in pieces:
        if len(current) + len(piece) + 1 <= chunk_size:
            current = f"{current} {piece}".strip()
        else:
            if current:
                chunks.append(current)
            # start next chunk with an overlap tail from the previous chunk
            tail = current[-overlap:] if overlap and current else ""
            current = f"{tail} {piece}".strip()

    if current:
        chunks.append(current)
    return chunks
