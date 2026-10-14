from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.core import ratelimit
from app.services import cloud_llm, cpu_inference, llm
from app.services.modal_client import WorkerUnavailable


@pytest.mark.anyio
@pytest.mark.parametrize("provider,host", [("xai", "api.x.ai"), ("groq", "api.groq.com")])
async def test_explicit_provider_and_no_fallback(monkeypatch, provider, host):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "redis_url", "")
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "llm_provider", provider)
    monkeypatch.setattr(cfg, "xai_api_key", "test-key")
    monkeypatch.setattr(cfg, "xai_model", "test-model")
    monkeypatch.setattr(cfg, "groq_api_key", "test-key")
    response = httpx.Response(429, request=httpx.Request("POST", "https://" + host))
    monkeypatch.setattr(cloud_llm, "_event", lambda event: None)
    if provider == "groq":
        from app.core import ratelimit
        monkeypatch.setattr(ratelimit, "reserve_provider_budget", lambda *args: (True, 0))
        monkeypatch.setattr(ratelimit, "provider_cooldown_remaining", lambda *args: 0)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        with pytest.raises(WorkerUnavailable, match="temporarily unavailable"):
            await llm.generate("safe test")
        assert post.await_count == 1
        assert httpx.URL(post.call_args.args[0]).host == host


@pytest.mark.anyio
async def test_xai_completion(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "llm_provider", "xai")
    monkeypatch.setattr(cfg, "xai_api_key", "test-key")
    monkeypatch.setattr(cfg, "xai_model", "configured-model")
    monkeypatch.setattr(cloud_llm, "_event", lambda event: None)
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.x.ai"),
        json={"choices": [{"message": {"content": "Hello"}}]})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        assert await cloud_llm.generate("test", "system") == "Hello"
        assert post.call_args.kwargs["json"]["model"] == "configured-model"


@pytest.mark.anyio
async def test_groq_uses_gpt_oss_completion_parameter_and_logs_safe_usage(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "local")
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "redis_url", "")
    monkeypatch.setattr(cfg, "llm_provider", "groq")
    monkeypatch.setattr(cfg, "groq_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(cfg, "groq_api_key", "secret-test-key")
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.groq.com"),
        json={"choices": [{"message": {"content": "A safe answer"}}],
              "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18}},
        headers={"x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "999",
                 "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7000"})
    recorded = []
    monkeypatch.setattr(cloud_llm, "_event", recorded.append)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        assert await cloud_llm.generate("test", task_type="ask_ai") == "A safe answer"
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "openai/gpt-oss-20b"
    assert payload["max_completion_tokens"] == 2048
    assert "max_tokens" not in payload
    assert recorded[0]["task_type"] == "ask_ai"
    assert recorded[0]["total_tokens"] == 18
    assert recorded[0]["rpd_limit"] == 1000
    assert recorded[0]["tpm_limit"] == 8000
    assert "secret-test-key" not in str(recorded[0])


@pytest.mark.anyio
async def test_groq_401_uses_secondary_once_but_429_never_rotates(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "local")
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "redis_url", "")
    monkeypatch.setattr(cfg, "llm_provider", "groq")
    monkeypatch.setattr(cfg, "groq_api_key", "primary-secret")
    monkeypatch.setattr(cfg, "groq_api_key_secondary", "secondary-secret")
    monkeypatch.setattr(cloud_llm, "_event", lambda event: None)
    request = httpx.Request("POST", "https://api.groq.com")
    unauthorized = httpx.Response(401, request=request)
    success = httpx.Response(200, request=request,
        json={"choices": [{"message": {"content": "recovered"}}]})
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=[unauthorized, success])) as post:
        assert await cloud_llm.generate("test") == "recovered"
        assert post.await_count == 2
        assert post.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer primary-secret"
        assert post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer secondary-secret"

    monkeypatch.setattr(cfg, "groq_api_key_secondary", "secondary-secret")
    cooldowns = []
    monkeypatch.setattr(ratelimit, "provider_cooldown", lambda model, seconds, cfg: cooldowns.append(seconds))
    rate_limited = httpx.Response(429, request=request, headers={
        "x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "10h12m",
    })
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=rate_limited)) as post:
        with pytest.raises(WorkerUnavailable):
            await cloud_llm.generate("test")
        assert post.await_count == 1
        assert cooldowns == [36720]


@pytest.mark.anyio
async def test_groq_5xx_retries_are_bounded(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "local")
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "redis_url", "")
    monkeypatch.setattr(cfg, "llm_provider", "groq")
    monkeypatch.setattr(cfg, "groq_api_key", "test-key")
    monkeypatch.setattr(cloud_llm, "_event", lambda event: None)
    response = httpx.Response(503, request=httpx.Request("POST", "https://api.groq.com"))
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        with pytest.raises(WorkerUnavailable):
            await cloud_llm.generate("test")
        assert post.await_count == 3


def test_groq_duration_header_parser():
    assert cloud_llm._reset_seconds("1m23.4s") == 83
    assert cloud_llm._reset_seconds("8") == 8
    assert cloud_llm._reset_seconds("unknown") is None


def test_api_process_cannot_load_heavy_models(monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_process", False)
    with pytest.raises(WorkerUnavailable, match="queue worker"):
        cpu_inference.embed(["test"])
    with pytest.raises(WorkerUnavailable, match="queue worker"):
        cpu_inference.whisper()


def test_cloud_provider_budget_fails_closed_without_shared_redis(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "redis_url", "")
    monkeypatch.setattr(ratelimit, "_redis", lambda: None)
    with pytest.raises(ratelimit.RateLimitUnavailable):
        ratelimit.reserve_provider_budget("openai/gpt-oss-20b", 100, cfg)


def test_cloud_provider_budget_uses_shared_atomic_limiter(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "environment", "development")
    calls = []

    class FakeRedis:
        def eval(self, script, key_count, *args):
            calls.append((key_count, args))
            return [1, 0, 0]

    monkeypatch.setattr(ratelimit, "_redis", lambda: FakeRedis())
    assert ratelimit.reserve_provider_budget("openai/gpt-oss-20b", 432, cfg) == (True, 0)
    assert calls[0][0] == 4
    assert calls[0][1][-5:] == (cfg.groq_safe_rpm, cfg.groq_safe_rpd, cfg.groq_safe_tpm, cfg.groq_safe_tpd, 432)
