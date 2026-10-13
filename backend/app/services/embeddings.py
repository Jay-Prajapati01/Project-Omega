"""Embedding generation with a provider-independent interface.

Providers (selected by EMBEDDING_PROVIDER):
* ollama — local Ollama batch /api/embed endpoint (nomic-embed-text default).
* gemini — Google Gemini REST API (gemini-embedding-2 default, Matryoshka
  truncation to EMBEDDING_DIM, default 768).

Modal/CPU overrides predate the provider switch and keep working: modal mode
routes through the Modal worker, legacy cloud mode through local CPU
inference — both only when EMBEDDING_PROVIDER=ollama.

Gemini integration details:
* batchEmbedContents is called with exactly ONE request entry per chunk, so
  every stored chunk gets its own vector. gemini-embedding-2 aggregates
  multiple inputs of a single embedContent call into one vector — sending a
  whole batch as one input would silently collapse chunks.
* Indexed documents use taskType RETRIEVAL_DOCUMENT, search queries use
  RETRIEVAL_QUERY; the cache key covers provider, model, dimension and
  purpose so query and document vectors never collide.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com"
_GEMINI_BATCH_SIZE = 32
_GEMINI_MAX_CHARS = 10000  # well under the ~2048-token input limit

_CACHE_MAX = 2048
_cache: OrderedDict[str, list[float]] = OrderedDict()


def _key(text: str, purpose: str) -> str:
    settings = get_settings()
    scope = "|".join((
        settings.embedding_provider,
        settings.embedding_model,
        str(settings.embedding_dim_for_model),
        purpose,
    ))
    return hashlib.sha256(f"{scope}|{text}".encode("utf-8")).hexdigest()


def _cache_get(key: str) -> list[float] | None:
    vec = _cache.get(key)
    if vec is not None:
        _cache.move_to_end(key)
    return vec


def _cache_put(key: str, vec: list[float]) -> None:
    _cache[key] = vec
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def reset_cache_for_tests() -> None:
    _cache.clear()


async def _embed_batch(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    """Embed a batch: try modern /api/embed, fall back to per-prompt /api/embeddings."""
    settings = get_settings()
    try:
        resp = await client.post(
            "/api/embed",
            json={"model": settings.embedding_model, "input": texts, "truncate": False},
        )
        if resp.status_code in (404, 405):
            raise httpx.HTTPStatusError("batch endpoint unavailable", request=resp.request, response=resp)
        if resp.status_code >= 400:
            body = resp.text[:300]
            if "context length" in body:
                # Oversized input: retry with truncation instead of failing
                # the whole ingestion pipeline.
                logger.warning("Ollama rejected oversized input; retrying with truncate=true")
                resp = await client.post(
                    "/api/embed",
                    json={"model": settings.embedding_model, "input": texts, "truncate": True},
                )
                if resp.status_code < 400:
                    return resp.json()["embeddings"]
                body = resp.text[:300]
            # Surface Ollama's actual reason (raise_for_status drops the body).
            raise RuntimeError(
                f"Ollama /api/embed returned {resp.status_code}: "
                f"{body} (input length={sum(len(t) for t in texts)} chars)"
            )
        return resp.json()["embeddings"]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (404, 405):
            raise
        logger.debug("Ollama /api/embed unavailable, using /api/embeddings per text")
        vectors: list[list[float]] = []
        for text in texts:
            r = await client.post(
                "/api/embeddings",
                json={"model": settings.embedding_model, "prompt": text},
            )
            r.raise_for_status()
            vectors.append(r.json()["embedding"])
        return vectors


async def _embed_gemini(texts: list[str], purpose: str) -> list[list[float]]:
    """Embed via the Gemini REST API — one vector per input text, always."""
    settings = get_settings()
    model = settings.embedding_model
    dim = settings.embedding_dim_for_model
    task_type = "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"
    base = (settings.gemini_api_base or GEMINI_API_BASE).rstrip("/")
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(base_url=base, timeout=120) as client:
        for start in range(0, len(texts), _GEMINI_BATCH_SIZE):
            batch = texts[start:start + _GEMINI_BATCH_SIZE]
            requests = [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": t[:_GEMINI_MAX_CHARS]}]},
                    "taskType": task_type,
                    "outputDimensionality": dim,
                }
                for t in batch
            ]
            resp = await client.post(f"/v1beta/models/{model}:batchEmbedContents", json={"requests": requests}, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"Gemini batchEmbedContents returned {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
            items = payload.get("embeddings", [])
            if len(items) != len(batch):
                raise RuntimeError(
                    f"Gemini returned {len(items)} embeddings for {len(batch)} texts; refusing a partial batch"
                )
            for item in items:
                values = item.get("values", [])
                if len(values) != dim:
                    raise RuntimeError(
                        f"Gemini returned dim={len(values)}, expected {dim}; refusing to mix vector spaces"
                    )
                vectors.append(values)
    return vectors


async def embed_texts(texts: list[str], purpose: str = "document") -> list[list[float]]:
    """Return one embedding vector per input text (cached, batched).

    purpose is "document" for indexed chunks and "query" for search/ask
    inputs; providers that distinguish retrieval roles (Gemini taskType) and
    the cache key both honour it.
    """
    if not texts:
        return []

    settings = get_settings()
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        keys = [_key(t, purpose) for t in texts]
        results: list[list[float] | None] = [_cache_get(k) for k in keys]
        missing_idx = [i for i, v in enumerate(results) if v is None]
        if missing_idx:
            vectors = await _embed_gemini([texts[i] for i in missing_idx], purpose)
            for i, vec in zip(missing_idx, vectors):
                results[i] = vec
                _cache_put(keys[i], vec)
        return [v for v in results if v is not None]

    if settings.mindmesh_execution_mode == "cloud":
        import asyncio
        from app.services.cpu_inference import embed
        return await asyncio.to_thread(embed, texts)

    if settings.mindmesh_execution_mode == "modal":
        from app.services.modal_client import embed
        return await embed(texts)

    keys = [_key(t, purpose) for t in texts]
    results = [_cache_get(k) for k in keys]
    missing_idx = [i for i, v in enumerate(results) if v is None]
    if not missing_idx:
        return [v for v in results if v is not None]

    missing_texts = [texts[i] for i in missing_idx]
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=120) as client:
        vectors = await _embed_batch(client, missing_texts)
    if len(vectors) != len(missing_texts):
        raise RuntimeError(
            f"Ollama returned {len(vectors)} embeddings for {len(missing_texts)} texts"
        )

    for i, vec in zip(missing_idx, vectors):
        results[i] = vec
        _cache_put(keys[i], vec)
    return [v for v in results if v is not None]


async def embed_text(text: str, purpose: str = "document") -> list[float]:
    """Convenience wrapper for embedding a single string."""
    result = await embed_texts([text], purpose=purpose)
    return result[0]
