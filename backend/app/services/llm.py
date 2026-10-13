"""LLM completion with adaptive backend selection.

Priority (see `app.core.backend_config`):
1. Groq Cloud   – `GROQ_API_KEY` set  → OpenAI-compatible chat completions
2. HF Spaces    – `HF_SPACE_URL` set  → POST `{space}/generate`
3. Local        – default             → Ollama (`/api/generate`)

Modal execution mode (`mindmesh_execution_mode == "modal"`) overrides the
selection and routes to the remote worker instead.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1"
BACKEND_TIMEOUT = 180.0


def _groq_headers(bcfg: dict) -> dict:
    return {"Authorization": f"Bearer {bcfg['key']}"}


def _chat_messages(prompt: str, system: str | None) -> list[dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


async def generate(prompt: str, system: str | None = None) -> str:
    """Generate a completion from the active AI backend."""
    settings = get_settings()
    if settings.mindmesh_execution_mode == "cloud":
        from app.services.cloud_llm import generate as cloud_generate
        return await cloud_generate(prompt, system)
    if settings.mindmesh_execution_mode == "modal":
        from app.services.modal_client import generate as remote_generate
        return await remote_generate(prompt, system)

    from app.core.backend_config import backend, is_groq, is_hf

    if is_groq():
        bcfg = backend()
        payload = {
            "model": bcfg["model"],
            "messages": _chat_messages(prompt, system),
            "stream": False,
        }
        async with httpx.AsyncClient(base_url=GROQ_API_BASE, timeout=BACKEND_TIMEOUT) as client:
            resp = await client.post(
                "/chat/completions", json=payload, headers=_groq_headers(bcfg)
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    if is_hf():
        bcfg = backend()
        payload = {"prompt": prompt, "system": system, "stream": False}
        async with httpx.AsyncClient(
            base_url=bcfg["space_url"].rstrip("/"), timeout=BACKEND_TIMEOUT
        ) as client:
            resp = await client.post("/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    payload: dict = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        resp = await client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


async def generate_stream(
    prompt: str, system: str | None = None
) -> AsyncIterator[str]:
    """Stream tokens from the active AI backend."""
    if get_settings().mindmesh_execution_mode in {"modal", "cloud"}:
        yield await generate(prompt, system)
        return

    from app.core.backend_config import backend, is_groq, is_hf

    if is_hf():
        # HF worker has no token streaming – yield the single response.
        yield await generate(prompt, system)
        return

    if is_groq():
        bcfg = backend()
        payload = {
            "model": bcfg["model"],
            "messages": _chat_messages(prompt, system),
            "stream": True,
        }
        async with httpx.AsyncClient(base_url=GROQ_API_BASE, timeout=BACKEND_TIMEOUT) as client:
            async with client.stream(
                "POST", "/chat/completions", json=payload, headers=_groq_headers(bcfg)
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        token = json.loads(data)["choices"][0]["delta"].get("content")
                    except (ValueError, KeyError, IndexError) as exc:
                        logger.debug("Failed to parse Groq stream chunk: %s", exc)
                        continue
                    if token:
                        yield token
        return

    settings = get_settings()
    payload: dict = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": True,
    }
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        async with client.stream("POST", "/api/generate", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield token
                except Exception as e:
                    logger.debug("Failed to parse LLM stream chunk: %s", e)
                    continue
