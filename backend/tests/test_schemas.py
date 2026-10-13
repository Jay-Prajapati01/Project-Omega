"""Tests for Pydantic schemas."""
from app.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    SourceItem,
    StatsResponse,
    SearchRequest,
)


def test_chat_message():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_request_with_history():
    history = [
        ChatMessage(role="user", content="What is AI?"),
        ChatMessage(role="assistant", content="AI is artificial intelligence."),
    ]
    req = ChatRequest(question="Tell me more", history=history)
    assert len(req.history) == 2
    assert req.history[0].role == "user"
    assert req.top_k is None
    assert req.source_type is None


def test_chat_request_defaults():
    req = ChatRequest(question="test")
    assert req.history == []
    assert req.top_k is None


def test_chat_response():
    resp = ChatResponse(
        question="test",
        answer="test answer",
        citations=[],
        search_time_ms=100,
        chunks_searched=5,
        sources_searched=2,
    )
    assert resp.search_time_ms == 100
    assert resp.chunks_searched == 5


def test_citation():
    c = Citation(
        source_id="abc123",
        source_type="youtube",
        title="Test Video",
        snippet="A snippet",
        url="https://youtube.com/watch?v=abc123",
    )
    assert c.source_id == "abc123"
    assert c.url is not None


def test_source_item():
    item = SourceItem(
        source_id="test123",
        source_type="pdf",
        title="Test Doc",
        file_size=1024,
        page_count=10,
    )
    assert item.page_count == 10
    assert item.file_size == 1024


def test_source_item_defaults():
    item = SourceItem(source_id="x", source_type="pdf")
    assert item.page_count is None
    assert item.file_size is None
    assert item.key_topics == []
    assert item.chunks_indexed == 0


def test_stats_response():
    stats = StatsResponse(
        indexed_chunks=100,
        total_sources=5,
        sources_by_type={"youtube": 2, "pdf": 3},
    )
    assert stats.vector_store == "qdrant"
    assert stats.total_files_stored == 0


def test_search_request():
    req = SearchRequest(query="test query", top_k=10, source_type="pdf")
    assert req.top_k == 10
    assert req.source_type == "pdf"
