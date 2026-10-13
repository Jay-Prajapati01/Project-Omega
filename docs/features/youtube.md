# YouTube feature

## Website flow

The `/youtube` page submits a video URL to `POST /api/videos/process` (and has a streaming path). The handler reserves tenant feature quota, validates/extracts the video ID, fetches metadata, obtains a transcript, summarizes it, chunks and embeds the text, then writes the source and vectors to the scoped store. The result appears in Stored and can be queried by Ask AI.

## Extraction tools and fallback

- `yt-dlp` fetches video metadata without downloading media and downloads audio only when transcript APIs cannot provide text.
- `youtube-transcript-api` selects an available transcript, preferring a suitable generated or human transcript.
- `faster-whisper` transcribes the downloaded audio fallback. `ffmpeg` is needed for audio extraction/runtime support.
- The shared LLM and embedding providers produce summaries, topic labels, and vectors.

Input hosts are checked by the YouTube URL parser. The browser gets progress events on the streaming endpoint. The Android companion submits YouTube shares through `/api/mobile/quick-saves`, which queues the same ingestion handler.

## Important limits

Transcript availability and platform throttling depend on the video and YouTube. A video without an accessible transcript may require a successful audio download and local/worker transcription.
