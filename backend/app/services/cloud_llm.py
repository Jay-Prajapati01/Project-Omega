"""Explicit production LLM provider; never fallback or expose provider errors."""
import httpx

from app.core.config import get_settings
from app.services.modal_client import WorkerUnavailable


async def generate(prompt: str, system: str | None = None) -> str:
    cfg = get_settings()
    if cfg.llm_provider == "xai":
        base, key, model = "https://api.x.ai/v1", cfg.xai_api_key, cfg.xai_model
    elif cfg.llm_provider == "groq":
        base, key, model = "https://api.groq.com/openai/v1", cfg.groq_api_key, cfg.groq_model
    else:
        raise WorkerUnavailable("LLM provider is not configured")
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                base + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={"model": model, "messages": messages, "stream": False, "max_tokens": 2048},
            )
            response.raise_for_status()
            answer = response.json()["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty completion")
            return answer.strip()
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        raise WorkerUnavailable("LLM temporarily unavailable") from None
