from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.services import cloud_llm, cpu_inference, llm
from app.services.modal_client import WorkerUnavailable


@pytest.mark.anyio
@pytest.mark.parametrize("provider,host", [("xai", "api.x.ai"), ("groq", "api.groq.com")])
async def test_explicit_provider_and_no_fallback(monkeypatch, provider, host):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "llm_provider", provider)
    monkeypatch.setattr(cfg, "xai_api_key", "test-key")
    monkeypatch.setattr(cfg, "xai_model", "test-model")
    monkeypatch.setattr(cfg, "groq_api_key", "test-key")
    response = httpx.Response(429, request=httpx.Request("POST", "https://" + host))
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        with pytest.raises(WorkerUnavailable, match="temporarily unavailable"):
            await llm.generate("safe test")
        assert post.await_count == 1
        assert httpx.URL(post.call_args.args[0]).host == host


@pytest.mark.anyio
async def test_xai_completion(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "llm_provider", "xai")
    monkeypatch.setattr(cfg, "xai_model", "configured-model")
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.x.ai"),
        json={"choices": [{"message": {"content": "Hello"}}]})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        assert await cloud_llm.generate("test", "system") == "Hello"
        assert post.call_args.kwargs["json"]["model"] == "configured-model"


def test_api_process_cannot_load_heavy_models(monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_process", False)
    with pytest.raises(WorkerUnavailable, match="queue worker"):
        cpu_inference.embed(["test"])
    with pytest.raises(WorkerUnavailable, match="queue worker"):
        cpu_inference.whisper()
