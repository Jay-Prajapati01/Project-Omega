"""Shared faster-whisper model singleton.

Loading WhisperModel takes seconds and hundreds of MB. Every transcript path
(uploads, YouTube fallback, Instagram reels) must reuse one instance instead
of reloading it per request.
"""
from __future__ import annotations

import threading

from app.core.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_model = None

MODEL_NAME = "base"


def get_model():
    """Return the process-wide WhisperModel, loading it on first use."""
    from app.core.tenant import cloud
    from app.core.config import get_settings
    if get_settings().mindmesh_execution_mode == "cloud":
        from app.services.cpu_inference import whisper
        return whisper()
    if cloud():
        return _RemoteWhisper()
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel

                logger.info("Loading faster-whisper model '%s'", MODEL_NAME)
                _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


class _RemoteWhisper:
    def transcribe(self, path, **kwargs):
        from types import SimpleNamespace
        from app.services.modal_client import transcribe
        segments = transcribe(str(path))
        return (SimpleNamespace(**segment) for segment in segments), None
