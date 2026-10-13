# Pipelines and tools

## Interactive website ingestion

`Next.js page → FastAPI validation/auth/quota → source extractor → transcript/text → shared summarizer → text chunker → embedding provider → Qdrant + scoped source store → Stored and Ask AI`.

## Cloud execution

When configured for Modal/cloud, the selected API facade validates and enqueues tenant-owned jobs. The configured worker executes the same video/Instagram/chat handler under a verified tenant envelope. Job status is returned to the website or companion. The source includes Modal and Google Cloud Tasks/Run adapters; choose and configure one deployment mode using the environment template and deployment docs retained from source only where needed.

## Feature tool map

| Feature | Main tools | Fallback / storage |
| --- | --- | --- |
| YouTube | `yt-dlp`, `youtube-transcript-api` | `faster-whisper`; shared chunking, embeddings, Qdrant, source store |
| Instagram | Playwright, Instaloader | Tesseract OCR and Whisper where accessible; shared chunking, embeddings, Qdrant, source store |
| Ask AI | RAG service, hybrid relevance ranker, configured LLM, embedding provider | Qdrant plus workspace notes; cited answer and ranked source cards |
| Stored | FastAPI sources/notes APIs | Tenant-scoped metadata/content store and Qdrant vectors; discovery lives in Ask AI |
| Companion | Android Compose, Room, WorkManager, Retrofit | Local durable queue, idempotent API save, status polling |

The backend retains low-level modules shared by the selected routes, but the API routers and cloud job registry expose only the selected ingestion and retrieval paths plus health, account, and admin support endpoints.
