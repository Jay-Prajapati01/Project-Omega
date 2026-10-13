"""Tests for the PDF pipeline services."""
from __future__ import annotations



class TestPdfValidator:
    def test_empty_data(self):
        from app.services.pdf_validator import validate
        result = validate(b"", "test.pdf")
        assert result.valid is False
        assert "Empty file" in result.errors[0]

    def test_invalid_magic_bytes(self):
        from app.services.pdf_validator import validate
        result = validate(b"NOT A PDF", "test.pdf")
        assert result.valid is False
        assert "Not a valid PDF" in result.errors[0]

    def test_valid_pdf_header(self):
        from app.services.pdf_validator import validate
        # Minimal valid PDF header
        data = b"%PDF-1.4\n" + b"\x00" * 100
        result = validate(data, "test.pdf")
        assert result.valid is True

    def test_file_too_large(self):
        from app.services.pdf_validator import validate
        from app.services.pdf_validator import _MAX_FILE_SIZE
        data = b"%PDF" + b"\x00" * (_MAX_FILE_SIZE + 1)
        result = validate(data, "test.pdf")
        assert result.valid is False
        assert "maximum size" in result.errors[0].lower()


class TestPdfCleaner:
    def test_empty_text(self):
        from app.services.pdf_cleaner import clean_text
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_whitespace_normalization(self):
        from app.services.pdf_cleaner import clean_text
        text = "Hello   world\t\t\n\n\n\n  test"
        result = clean_text(text)
        assert "   " not in result
        assert "\t" not in result

    def test_clean_markdown(self):
        from app.services.pdf_cleaner import clean_markdown
        md = "# Heading\n\n\n\nParagraph\n\n"
        result = clean_markdown(md)
        assert "\n\n\n" not in result


class TestPdfChunker:
    def test_empty_text(self):
        from app.services.pdf_chunker import chunk_text
        assert chunk_text("") == []
        assert chunk_text(None) == []

    def test_short_text_single_chunk(self):
        from app.services.pdf_chunker import chunk_text
        result = chunk_text("Hello world.")
        assert len(result) == 1
        assert result[0] == "Hello world."

    def test_long_text_multiple_chunks(self):
        from app.services.pdf_chunker import chunk_text
        text = ". ".join([f"Sentence {i}" for i in range(50)])
        result = chunk_text(text, chunk_size=100, overlap=20)
        assert len(result) > 1

    def test_chunk_document_with_headings(self):
        from app.services.pdf_chunker import chunk_document
        md = "## Introduction\nSome intro text.\n\n## Methods\nSome method text.\n\n## Conclusion\nSome conclusion."
        result = chunk_document(md, chunk_size=200)
        assert len(result) > 0
        assert all("text" in c for c in result)
        assert all("section_heading" in c for c in result)


class TestPdfMetadata:
    def test_metadata_from_bytes(self):
        from app.services.pdf_metadata import extract_metadata
        # Minimal PDF structure
        data = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 0\ntrailer<</Size 0>>\nstartxref\n0\n%%EOF"
        meta = extract_metadata(data, "test.pdf")
        assert meta.file_size == len(data)
        assert meta.title == "Test"  # Derived from filename
