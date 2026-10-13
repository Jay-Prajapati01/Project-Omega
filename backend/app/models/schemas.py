"""Pydantic request/response models shared across the API."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    environment: str
    version: str


class VideoProcessRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="YouTube video URL")


class VideoMetadata(BaseModel):
    video_id: str
    title: str | None = None
    channel: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    published_at: str | None = None


class VideoProcessResponse(BaseModel):
    video_id: str
    metadata: VideoMetadata
    summary: str | None = None
    key_topics: list[str] = []
    chunks_indexed: int = 0
    processed_at: datetime = Field(default_factory=_utcnow)


def _clean_text(value: str, field_name: str, max_len: int) -> str:
    """Normalize user text (trim) and reject oversized input with a 422.

    Blank input is allowed by the schema so the endpoints can answer
    gracefully instead of erroring; handlers short-circuit empty values.
    """
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise ValueError(f"{field_name} must be at most {max_len} characters")
    return cleaned


class SearchRequest(BaseModel):
    query: str
    # Bounded: an unbounded top_k lets a caller materialize the entire
    # collection in the app process (or 500 on negative values).
    top_k: int | None = Field(default=None, ge=1, le=50)
    source_type: str | None = Field(
        default=None, max_length=32, description="Optional filter by source type"
    )

    @field_validator("query", mode="after")
    @classmethod
    def _validate_query(cls, v: str) -> str:
        return _clean_text(v, "query", 1000)


class SearchHit(BaseModel):
    score: float
    text: str
    source_id: str
    source_type: str
    title: str | None = None
    url: str | None = None
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    search_time_ms: int = 0
    chunks_searched: int = 0
    sources_searched: int = 0


class ChatMessage(BaseModel):
    role: str = Field(..., max_length=16)  # "user" or "assistant"
    content: str = Field(..., max_length=20000)


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = Field(default=None, max_length=128)
    top_k: int | None = Field(default=None, ge=1, le=50)
    source_type: str | None = Field(default=None, max_length=32)
    source_id: str | None = Field(default=None, max_length=128)
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)

    @field_validator("question", mode="after")
    @classmethod
    def _validate_question(cls, v: str) -> str:
        return _clean_text(v, "question", 4000)


class Citation(BaseModel):
    source_id: str
    source_type: str
    title: str | None = None
    snippet: str
    url: str | None = None
    thumbnail: str | None = None
    score: float = 0.0


class ChatResponse(BaseModel):
    question: str
    conversation_id: str | None = None
    answer: str
    citations: list[Citation]
    related_sources: list[SearchHit] = Field(default_factory=list)
    search_time_ms: int | None = None
    chunks_searched: int | None = None
    sources_searched: int | None = None


class SourceItem(BaseModel):
    """A record of an ingested source (video, pdf, etc.)."""

    source_id: str
    source_type: str
    title: str | None = None
    channel: str | None = None
    thumbnail: str | None = None
    summary: str | None = None
    key_topics: list[str] = []
    chunks_indexed: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    url: str | None = None
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    page_count: int | None = None


class RecentQuery(BaseModel):
    text: str
    created_at: datetime = Field(default_factory=_utcnow)


class PDFDocument(BaseModel):
    """Structured output from the PDF pipeline."""

    title: str = ""
    author: str | None = None
    creation_date: str | None = None
    page_count: int = 0
    language: str | None = None
    file_size: int = 0
    document_type: str = "unknown"
    headings: list[str] = []
    sections: list[dict] = []
    tables: list[dict] = []
    images: list[dict] = []
    paragraphs: list[str] = []
    captions: list[str] = []
    metadata: dict = {}
    markdown: str = ""
    chunks: list[dict] = []
    needs_ocr: bool = False


class StatsResponse(BaseModel):
    indexed_chunks: int
    total_sources: int
    sources_by_type: dict[str, int]
    vector_store: str = "qdrant"
    total_files_stored: int = 0
    total_storage_bytes: int = 0
    recent_sources: list[SourceItem] = []
    recent_searches: list[RecentQuery] = []
    recent_questions: list[RecentQuery] = []
    knowledge_growth: list[dict] = []
