"""Adaptive AI backend selection for MindMesh.

Selects the best available LLM backend in this priority:
1. Groq Cloud (free tier: 30 RPM, 30K TPM, 500K TPD) – fastest, GPU-accelerated
2. Hugging Face Spaces (free tier – CPU, slower but no cost)
3. Local workers (transformers on CPU) – free, private, no API dependencies

The selection respects environment variables so the same code works
locally, on Render, or on Hugging Face Spaces.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, Optional


class BackendType(Enum):
    GROQ = "groq"        # Groq Cloud API
    HF_SPACES = "hf_spaces"  # Hugging Face Spaces (CPU)
    LOCAL = "local"      # Local transformers / yt-dlp / Docling


# ---------------------------------------------------------------------------
# Backend configuration – populated from environment at module import.
# ---------------------------------------------------------------------------
_BACK: Optional[Dict] = None


def _init() -> None:
    """Load backend configuration from process environment once."""
    global _BACK

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    hf_url = os.getenv("HF_SPACE_URL", "").strip()

    if groq_key:
        _BACK = {
            "type": BackendType.GROQ,
            "key": groq_key,
            "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            "rpm_limit": int(os.getenv("GROQ_RPM_LIMIT", "30")),
            "tpm_limit": int(os.getenv("GROQ_TPM_LIMIT", "30000")),
            "tpd_limit": int(os.getenv("GROQ_TPD_LIMIT", "500000")),
        }
    elif hf_url:
        _BACK = {
            "type": BackendType.HF_SPACES,
            "space_url": hf_url,
            # No model name needed – we use local transformers models.
        }
    else:
        _BACK = {
            "type": BackendType.LOCAL,
            # No extra keys needed – we use local transformers / yt-dlp.
        }


_init()  # populate _BACK once at import time


def backend() -> Dict:
    """Return the current backend configuration dict."""
    return _BACK


def is_groq() -> bool:
    return _BACK["type"] is BackendType.GROQ


def is_hf() -> bool:
    return _BACK["type"] is BackendType.HF_SPACES


def is_local() -> bool:
    return _BACK["type"] is BackendType.LOCAL


# ---------------------------------------------------------------------------
# Helper – human‑readable name (used in API responses, logs, UI).
# ---------------------------------------------------------------------------
def backend_name() -> str:
    """Return a short label for the active backend."""
    return _BACK["type"].value


# ---------------------------------------------------------------------------
# Legacy helper – kept for any code that still imports `get_settings`‑style.
# ---------------------------------------------------------------------------
def get_settings() -> Dict:
    """Back‑compatibility shim returning the same keys the old code expected."""
    b = backend()
    return {
        "groq_api_key": b.get("key", ""),
        "hf_space_url": b.get("space_url", ""),
        "backend": backend_name(),
    }