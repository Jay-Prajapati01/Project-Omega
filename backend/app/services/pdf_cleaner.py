"""PDF text cleaning: normalize whitespace, fix OCR artifacts, preserve structure."""
from __future__ import annotations

import re

from app.core.logging import get_logger

logger = get_logger(__name__)

# Common OCR artifacts
_OCR_FIXES: list[tuple[str, str]] = [
    (r"(?<=[a-z])\s+(?=[a-z](?:\.|$))", ""),  # Broken words
    (r"(?<=[A-Z])\s+(?=[A-Z](?:\.|$))", ""),  # Broken acronyms
    (r"\s+([,.;:!?\)])", r"\1"),  # Space before punctuation
    (r"\(\s+", "("),  # Space after opening paren
    (r"\s+\)", ")"),  # Space before closing paren
    (r"(?<!\w)--(?!\w)", "—"),  # Double dash to em dash
    (r"(?<!\w)---(?!\w)", "—"),  # Triple dash to em dash
]

_HEADING_PATTERNS = [
    re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE),  # Markdown headings
    re.compile(r"^([A-Z][A-Z\s]{2,})$", re.MULTILINE),  # ALL CAPS headings
    re.compile(r"^\d+(\.\d+)*\s+[A-Z].+$", re.MULTILINE),  # Numbered headings
]

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_MULTI_SPACES = re.compile(r"[ \t]{2,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)


def clean_text(text: str) -> str:
    """Clean and normalize extracted PDF text.

    Fixes common OCR artifacts, normalizes whitespace, and preserves
    document structure (headings, paragraphs).
    """
    if not text:
        return ""

    # Preserve heading markers before cleaning
    headings = _extract_headings(text)

    # Fix OCR artifacts
    for pattern, replacement in _OCR_FIXES:
        text = re.sub(pattern, replacement, text)

    # Normalize whitespace
    text = _MULTI_SPACES.sub(" ", text)
    text = _TRAILING_SPACES.sub("", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)

    # Re-insert heading markers
    for heading in headings:
        if heading not in text:
            text = text.replace(heading.upper(), f"## {heading}")

    return text.strip()


def clean_markdown(markdown: str) -> str:
    """Clean Docling-generated markdown output.

    Ensures consistent formatting and removes artifacts.
    """
    if not markdown:
        return ""

    # Normalize line endings
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")

    # Fix multiple blank lines
    markdown = _MULTI_BLANK_LINES.sub("\n\n", markdown)

    # Fix trailing spaces
    markdown = _TRAILING_SPACES.sub("", markdown)

    # Ensure headings have space after #
    markdown = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", markdown, flags=re.MULTILINE)

    # Fix table formatting (ensure pipes have consistent spacing)
    lines = markdown.split("\n")
    cleaned_lines = []
    for line in lines:
        if "|" in line and not line.strip().startswith("```"):
            # Table row - normalize pipe spacing
            parts = [p.strip() for p in line.split("|")]
            line = " | ".join(parts)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _extract_headings(text: str) -> list[str]:
    """Extract potential headings from text for preservation."""
    headings: list[str] = []
    for pattern in _HEADING_PATTERNS:
        for match in pattern.finditer(text):
            heading = match.group(0).strip()
            if len(heading) < 100:  # Skip very long matches
                headings.append(heading)
    return headings
