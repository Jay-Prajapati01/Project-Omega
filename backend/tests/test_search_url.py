import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.anyio
async def test_search_url_resolution():
    mock_hits = [
        # youtube
        {
            "score": 0.9,
            "text": "YouTube clip info",
            "source_id": "yt_123",
            "source_type": "youtube",
            "title": "YouTube Video",
            "url": "https://youtube.com/watch?v=yt_123",
        },
        # pdf (needs api/sources/download link)
        {
            "score": 0.85,
            "text": "PDF contents snippet",
            "source_id": "pdf_abc",
            "source_type": "pdf",
            "title": "Document title",
            "file_path": "files/pdf/pdf_abc.pdf",
        },
        # web
        {
            "score": 0.8,
            "text": "Web content",
            "source_id": "web_xyz",
            "source_type": "web",
            "title": "Web page",
            "url": "https://example.com/page",
        },
        # document (needs api/sources/download link)
        {
            "score": 0.75,
            "text": "Word file snippet",
            "source_id": "doc_def",
            "source_type": "document",
            "title": "Word doc",
            "file_path": "files/documents/doc_def.docx",
        }
    ]

    with patch("app.services.embeddings.embed_text", new_callable=AsyncMock) as mock_embed, \
         patch("app.services.vectorstore.search", return_value=mock_hits), \
         patch("app.services.store.add_search"):
         
        mock_embed.return_value = [0.1] * 384
        
        response = client.post("/api/search", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        hits = data["hits"]
        
        # Verify youtube URL is preserved
        assert hits[0]["url"] == "https://youtube.com/watch?v=yt_123"
        assert hits[0]["source_type"] == "youtube"

        # Verify pdf URL is resolved to api/sources download path
        assert hits[1]["url"] == "/api/sources/pdf_abc/download"
        assert hits[1]["source_type"] == "pdf"

        # Verify web URL is preserved
        assert hits[2]["url"] == "https://example.com/page"
        assert hits[2]["source_type"] == "web"

        # Verify document URL is resolved to api/sources download path
        assert hits[3]["url"] == "/api/sources/doc_def/download"
        assert hits[3]["source_type"] == "document"
