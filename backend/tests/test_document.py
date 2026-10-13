"""Tests for document type dispatch and simple extractors."""
import pytest

from app.services.document import extract_text


def test_txt_extraction():
    result = extract_text(b"hello world", "note.txt")
    assert result["text"] == "hello world"
    assert result["title"] == "note.txt"


def test_csv_extraction():
    result = extract_text(b"a,b,c\n1,2,3", "data.csv")
    assert "a | b | c" in result["text"]
    assert "1 | 2 | 3" in result["text"]


def test_markdown_extraction():
    result = extract_text(b"# Title\n\nBody text", "doc.md")
    assert "Title" in result["text"]


def test_unsupported_type_raises():
    with pytest.raises(ValueError):
        extract_text(b"data", "file.exe")
