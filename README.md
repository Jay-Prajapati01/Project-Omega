<div align="center">
  <img src="frontend/public/MindMesh_logo.png" alt="MindMesh" width="88" />
  <h1>MindMesh</h1>
  <p><strong>Your saved videos, connected to your knowledge.</strong></p>
  <p>A focused multi-tenant knowledge workspace with YouTube and Instagram capture, grounded AI chat, a searchable library, and an interactive knowledge graph.</p>
</div>

---

## Product scope

This repository contains the selected MindMesh experience:

- **YouTube** — ingest public video links, retrieve transcripts or transcribe audio, summarize, and index the result.
- **Instagram** — process supported public post and Reel links, combining captions with available OCR and audio transcription.
- **Ask AI** — ask questions across saved sources, receive grounded responses, citations, relevance-ranked source cards, and direct source links.
- **Stored** — browse, open, search, and manage saved sources and notes.
- **Knowledge Graph** — explore saved YouTube and Instagram sources as separate, source-correct feature clusters with draggable nodes, thumbnails, and links to original content.
- **Admin analytics** — authorized workspace owners/admins can view consented anonymous traffic and feature aggregates.
- **Android companion** — share YouTube or Instagram links into the same account and backend ingestion pipeline.

Public pricing has been removed while the product is in its launch-learning phase. Existing access controls and account limits remain in force.

## Architecture

| Area | Technology | Location |
| --- | --- | --- |
| Website | Next.js, React, TypeScript | [`frontend/`](frontend/) |
| API and processing | FastAPI, Python | [`backend/`](backend/) |
| Mobile companion | Kotlin, Jetpack Compose, Room, WorkManager | [`frontend/companion/`](frontend/companion/) |
| Tenant identity | Supabase Auth and server-verified workspace scope | frontend + backend |
| Local vector storage | Qdrant | `backend/data/` (generated locally; not committed) |
| Feature / setup docs | Markdown | [`docs/`](docs/) |

The main processing path is:

```text
Website or companion → FastAPI auth/tenant validation → provider extraction
→ transcript/text → summary and chunking → embeddings → tenant-scoped storage
→ Stored, Ask AI, and Knowledge Graph
```

The companion uses a durable local queue and retries; it submits only YouTube and Instagram links. It shares the backend pipeline with the website, rather than maintaining a separate mobile-only processor.

## Run locally

### Requirements

- Node.js and npm (see `frontend/package.json` for the app's supported versions).
- Python 3.11+ and `pip`.
- Supabase project credentials for hosted sign-in and multi-tenant mode, or the documented local auth setup.
- Ollama for local LLM/embedding work unless another supported provider is configured.
- `yt-dlp`, `ffmpeg`, and `faster-whisper` for the YouTube audio-transcription fallback.
- Playwright browser dependencies and Tesseract for the relevant Instagram browser/OCR extraction paths.

### Backend

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Edit `backend/.env` with local settings and your own credentials. Keep `AUTH_ENABLED=true` for authenticated website and companion API use. Apply the SQL migrations for the chosen database before using cloud mode.

### Website

In a second PowerShell window:

```powershell
cd frontend
Copy-Item cloud.env.example .env.local
npm ci
npm run dev
```

Set the Supabase public URL/key and `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`. Open `http://localhost:3000`; check the API at `http://localhost:8000/health`.

### Android companion

See [`docs/companion.md`](docs/companion.md) and [`docs/manual-setup.md`](docs/manual-setup.md). Configure the ignored `frontend/companion/local.properties`, then run `gradlew.bat assembleDebug` from `frontend/companion`. ADB USB forwarding and install steps are in the manual setup guide.

## Configuration and security

- Copy the checked-in example environment files and supply your own values. Never commit `.env`, `local.properties`, database exports, or provider keys.
- `NEXT_PUBLIC_*` values are public browser configuration only. Keep Supabase service keys, database passwords, and AI provider secrets server-side.
- Admin access is determined by verified server-side account/workspace roles; a hidden URL is not an authorization control.
- Analytics collection is off until consent is accepted. The admin view shows anonymous aggregates; see [`docs/admin-analytics-launch.md`](docs/admin-analytics-launch.md) for data fields, storage, migration, and retention notes.
- Local Qdrant, user files, and analytics data are generated under `backend/data/` and are intentionally excluded from source control.

## Documentation

Start at [`docs/README.md`](docs/README.md) for the documentation index. It links the feature pipelines, graph behavior, multi-tenancy and admin access, companion setup, troubleshooting history, and launch checklist.

## Current boundaries

- Instagram extraction supports publicly accessible content; private, removed, login-gated, region-limited, or throttled content may not be processable.
- YouTube transcript availability and provider throttling vary. Audio transcription is a fallback and requires the configured local/worker dependencies.
- AI responses and similarity scores are grounded ranking aids, not guarantees of correctness or calibrated probabilities.
- Cloud analytics requires applying `backend/migrations/202610140001_analytics.sql` to the configured Supabase/Postgres database.

## License and attribution

This is a focused project clone based on the MindMesh source project supplied for this workspace. Retain applicable license and attribution notices from the source when distributing it. This repository does not grant rights to third-party platform content or logos.
