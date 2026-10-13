# Instagram feature

## Website flow

The `/instagram` page submits a public post or reel URL to `POST /api/instagram/process` or its streaming endpoint. The backend validates the shortcode and fetches public content, extracts caption/owner/media information, combines available text with OCR and speech transcription, then summarizes, chunks, embeds, and stores it under the active tenant. Stored and Ask AI use the resulting source.

## Extraction tools and fallback

- Playwright renders the public Instagram page and parses embedded page data.
- Instaloader is the secondary extraction strategy and may require Instagram credentials for some content.
- Pillow and Tesseract (`pytesseract`) support OCR over image frames.
- The shared Whisper model transcribes speech from reel media when audio is accessible.
- Shared LLM, embedding, vector-store, and source-store services finish indexing.

The companion uses the mobile quick-save queue and only accepts Instagram URLs there. Private, login-gated, removed, rate-limited, or region-restricted content can fail because the source project intentionally fetches public content without a user session.
