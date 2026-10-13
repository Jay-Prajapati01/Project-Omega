"""Tests for the smart chunker."""
from app.services.chunking import chunk_text


def test_empty_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world. This is a test.", chunk_size=100)
    assert len(chunks) == 1
    assert "Hello world" in chunks[0]


def test_long_text_splits_into_multiple_chunks():
    sentence = "This is sentence number {}. ".format
    text = "".join(sentence(i) for i in range(200))
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    # every chunk should respect (roughly) the size bound
    assert all(len(c) <= 300 for c in chunks)


def test_whitespace_is_collapsed():
    chunks = chunk_text("a\n\n   b\t\tc", chunk_size=100)
    assert chunks == ["a b c"]
