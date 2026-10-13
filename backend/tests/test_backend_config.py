"""Adaptive AI backend selection: Groq -> HF Spaces -> local.

Covers `app.core.backend_config` (env-driven priority) and the routing in
`app.services.llm` (which HTTP path each backend takes).
"""
from __future__ import annotations

import os

import httpx
import pytest

from app.core import backend_config as bc
from app.core.config import get_settings
from app.services import llm

_VARS = (
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "HF_SPACE_URL",
    "GROQ_RPM_LIMIT",
    "GROQ_TPM_LIMIT",
    "GROQ_TPD_LIMIT",
)


@pytest.fixture(autouse=True)
def _isolate_backend_state():
    """Snapshot env + module state; restore both after every test."""
    saved_env = {k: os.environ.get(k) for k in _VARS}
    saved_back = bc._BACK
    yield
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    bc._BACK = saved_back


# --- backend_config priority -------------------------------------------------


def test_default_is_local(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    bc._init()
    assert bc.is_local()
    assert not bc.is_groq() and not bc.is_hf()
    assert bc.backend_name() == "local"
    assert "key" not in bc.backend()


def test_groq_key_selects_groq_with_limits(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_123")
    bc._init()
    assert bc.is_groq()
    assert bc.backend_name() == "groq"
    cfg = bc.backend()
    assert cfg["type"] is bc.BackendType.GROQ
    assert cfg["key"] == "gsk_test_123"
    assert cfg["model"] == "llama-3.1-8b-instant"
    assert cfg["rpm_limit"] == 30
    assert cfg["tpm_limit"] == 30000
    assert cfg["tpd_limit"] == 500000


def test_groq_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    bc._init()
    assert bc.backend()["model"] == "llama-3.3-70b-versatile"


def test_hf_url_selects_hf_spaces(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("HF_SPACE_URL", "https://foo.hf.space")
    bc._init()
    assert bc.is_hf() and not bc.is_groq()
    assert bc.backend_name() == "hf_spaces"
    assert bc.backend()["space_url"] == "https://foo.hf.space"


def test_groq_wins_over_hf(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("HF_SPACE_URL", "https://foo.hf.space")
    bc._init()
    assert bc.is_groq()


def test_settings_shim(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    bc._init()
    assert bc.get_settings() == {
        "groq_api_key": "k",
        "hf_space_url": "",
        "backend": "groq",
    }


# --- llm routing --------------------------------------------------------------


class _FakeResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self) -> None:  # pragma: no cover - success path
        pass

    def json(self) -> dict:
        return self._data


class _FakeStreamResponse:
    def __init__(self, lines: list[str]):
        self._lines = lines

    def raise_for_status(self) -> None:  # pragma: no cover - success path
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCM:
    def __init__(self, resp: _FakeStreamResponse):
        self._resp = resp

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._resp

    async def __aexit__(self, *exc) -> bool:
        return False


def _fake_async_client(capture: dict):
    """Build an httpx.AsyncClient double recording calls and canned replies."""

    class _Client:
        def __init__(self, base_url=None, timeout=None, **kwargs):
            capture["base_url"] = base_url

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, path, json=None, headers=None):
            capture.update(path=path, json=json, headers=headers)
            if path == "/chat/completions":
                return _FakeResponse(
                    {"choices": [{"message": {"content": "groq reply"}}]}
                )
            return _FakeResponse({"response": "local reply"})

        def stream(self, method, path, json=None, headers=None):
            capture.update(path=path, json=json, headers=headers, stream=True)
            if path == "/chat/completions":
                lines = [
                    'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                    'data: {"choices":[{"delta":{"content":"lo"}}]}',
                    "data: [DONE]",
                ]
            else:
                lines = ['{"response":"local reply"}']
            return _FakeStreamCM(_FakeStreamResponse(lines))

    return _Client


@pytest.mark.anyio
async def test_generate_routes_to_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_123")
    bc._init()
    capture: dict = {}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(capture))

    out = await llm.generate("hello", system="be brief")

    assert out == "groq reply"
    assert capture["base_url"] == llm.GROQ_API_BASE
    assert capture["path"] == "/chat/completions"
    assert capture["headers"]["Authorization"] == "Bearer gsk_test_123"
    assert capture["json"]["model"] == "llama-3.1-8b-instant"
    assert capture["json"]["stream"] is False
    assert capture["json"]["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello"},
    ]


@pytest.mark.anyio
async def test_generate_routes_to_ollama_by_default(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    bc._init()
    settings = get_settings()
    capture: dict = {}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(capture))

    out = await llm.generate("hello", system="sys")

    assert out == "local reply"
    assert capture["base_url"] == settings.ollama_url
    assert capture["path"] == "/api/generate"
    assert capture["json"]["model"] == settings.llm_model
    assert capture["json"]["system"] == "sys"


@pytest.mark.anyio
async def test_generate_routes_to_hf_space(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("HF_SPACE_URL", "https://foo.hf.space")
    bc._init()
    capture: dict = {}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(capture))

    out = await llm.generate("hello")

    assert out == "local reply"
    assert capture["base_url"] == "https://foo.hf.space"
    assert capture["path"] == "/generate"
    assert capture["json"]["prompt"] == "hello"


@pytest.mark.anyio
async def test_generate_stream_routes_to_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_123")
    bc._init()
    capture: dict = {}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(capture))

    tokens = [t async for t in llm.generate_stream("hi")]

    assert tokens == ["Hel", "lo"]
    assert capture["path"] == "/chat/completions"
    assert capture["json"]["stream"] is True
    assert capture["headers"]["Authorization"] == "Bearer gsk_test_123"


@pytest.mark.anyio
async def test_generate_stream_hf_yields_single_response(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("HF_SPACE_URL", "https://foo.hf.space")
    bc._init()
    capture: dict = {}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(capture))

    tokens = [t async for t in llm.generate_stream("hi")]

    assert tokens == ["local reply"]
    assert capture["path"] == "/generate"
