"""Audio ingestion: Faster-Whisper locally, Groq Whisper API in cloud mode."""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.whisper_model import get_model

logger = get_logger(__name__)

SUPPORTED = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".webm"}

# Groq's transcription endpoint rejects files larger than 25 MB per request.
# Bigger uploads fail fast with a clear message instead of a cryptic 413
# from upstream (client-side splitting is future work, not silent truncation).
_GROQ_MAX_BYTES = 25 * 1024 * 1024


def transcribe(data: bytes, filename: str) -> dict:
    """Transcribe audio bytes to text. Returns {title, text}."""
    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported audio type: {ext or filename}")

    if get_settings().mindmesh_execution_mode == "cloud":
        return _transcribe_groq(data, filename)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        model = get_model()
        segments, _ = model.transcribe(tmp.name)
        text = " ".join(seg.text for seg in segments).strip()

    return {"title": Path(filename).stem, "text": text}


def _transcribe_groq(data: bytes, filename: str) -> dict:
    """Transcribe via Groq's hosted Whisper API (no local model weights).

    Speaker diarization is NOT available through this endpoint — segments
    come back as plain text. Do not claim diarization parity for cloud audio.
    """
    import httpx

    cfg = get_settings()
    if not cfg.groq_api_key:
        raise RuntimeError("Cloud transcription requires GROQ_API_KEY")
    if len(data) > _GROQ_MAX_BYTES:
        raise ValueError(
            f"Audio file is {len(data) // (1024 * 1024)} MB; "
            "cloud transcription accepts at most 25 MB per file"
        )
    try:
        with httpx.Client(timeout=300) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {cfg.groq_api_key}"},
                files={"file": (Path(filename).name, data)},
                data={"model": cfg.groq_whisper_model, "response_format": "json"},
            )
            resp.raise_for_status()
            text = (resp.json().get("text") or "").strip()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Groq transcription request failed: {exc}") from None
    return {"title": Path(filename).stem, "text": text}
