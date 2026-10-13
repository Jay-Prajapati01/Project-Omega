"""Shared test fixtures.

API tests must be hermetic: they never call Ollama, Qdrant, or any other
network service. `hermetic` patches the service layer with in-process fakes
so `pytest tests` passes on a machine with no model server or vector DB.

`modal_app` builds a second application instance in modal (cloud) mode with
the Supabase token endpoint, membership resolver, cloud state and Qdrant all
mocked — used by the authorization and contract suites. No network, no DB.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# `app.main` builds its middleware stack at import time (module-level `app =
# create_app()`), so the auth mode has to be pinned before any test module
# imports it. backend/.env carries AUTH_ENABLED=true for the Android companion;
# the default suite still exercises the anonymous local workspace. Set
# AUTH_ENABLED explicitly in the process environment to opt out.
os.environ.setdefault("AUTH_ENABLED", "false")

from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Keep every test inside its own temp data directory.

    The default data_dir (/app/data) only exists in the Docker setup. On a
    bare CI runner the root filesystem is not writable, mkdir raises
    PermissionError and the app's global handler turns that into a 403 on
    every data-touching endpoint. Hermetic tests must never depend on it.
    """
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))

# Deterministic fake embedding — same input, same vector, no model needed.
_EMBED_DIM = 32

MODAL_TENANT_A = "11111111-1111-1111-1111-111111111111"
MODAL_TENANT_B = "33333333-3333-3333-3333-333333333333"
MODAL_USER_ID = "22222222-2222-2222-2222-222222222222"


def _vec(text: str) -> list[float]:
    seed = sum(ord(c) for c in text) % 997
    return [((seed + i) % 100) / 100 for i in range(_EMBED_DIM)]


def _fake_hits() -> list[dict]:
    return [
        {
            "text": "MindMesh is a knowledge base with citations.",
            "score": 0.91,
            "source_id": "test-source-1",
            "source_type": "web",
            "title": "Test Source",
            "url": "https://example.com/article",
            "thumbnail": None,
        }
    ]


async def _fake_embed_text(text: str, purpose: str = "document") -> list[float]:
    return _vec(text)


async def _fake_embed_texts(texts: list[str], purpose: str = "document") -> list[list[float]]:
    return [_vec(t) for t in texts]


async def _fake_generate(prompt: str, system: str | None = None) -> str:
    return "This is a mocked LLM answer used by the test suite."


async def _fake_generate_stream(
    prompt: str, system: str | None = None
) -> AsyncIterator[str]:
    for token in ["Mocked ", "streamed ", "answer."]:
        yield token


def _fake_search(query_vec, top_k=None, source_type=None, source_id=None, **kwargs):
    return _fake_hits()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _rate_limits_off():
    """Rate limiting is exercised explicitly in test_rate_limit.py.

    Without this, cumulative in-process counters across the whole suite would
    eventually 429 unrelated tests.
    """
    from app.core.config import get_settings
    from app.core import ratelimit

    settings = get_settings()
    previous = settings.rate_limit_enabled
    settings.rate_limit_enabled = False
    ratelimit.reset_for_tests()
    yield
    settings.rate_limit_enabled = previous
    ratelimit.reset_for_tests()


@pytest.fixture(autouse=True)
def _anonymous_local_mode():
    """Pin auth off so a developer's .env cannot change test results.

    `get_settings()` reads backend/.env once. That file may carry
    AUTH_ENABLED=true for the Android companion, which correctly turns every
    unauthenticated route into a 401 — the default suite, though, exercises the
    anonymous local-workspace API. Auth-enabled behaviour is covered
    explicitly by test_auth_matrix.py / test_personal_workspace_auth.py and by
    any test that sets `auth_enabled` itself.
    """
    from app.core.config import get_settings

    settings = get_settings()
    previous = settings.auth_enabled
    settings.auth_enabled = False
    yield
    settings.auth_enabled = previous


@pytest.fixture
def hermetic() -> Iterator[None]:
    """Patch embeddings / vector search / LLM so API tests need no services."""
    with (
        patch("app.services.embeddings.embed_text", _fake_embed_text),
        patch("app.services.embeddings.embed_texts", _fake_embed_texts),
        patch("app.services.vectorstore.search", _fake_search),
        patch("app.services.vectorstore.count", lambda: len(_fake_hits())),
        patch("app.services.llm.generate", _fake_generate),
        patch("app.services.llm.generate_stream", _fake_generate_stream),
    ):
        yield


# --- Modal (cloud) mode app instance -----------------------------------------


class _AuthState:
    """Mutable authentication backend double for CloudAuthMiddleware."""

    def __init__(self) -> None:
        from app.core.tenant import Scope

        self.token_status = 200
        self.user_id = MODAL_USER_ID
        self.scope = Scope(MODAL_TENANT_A, MODAL_USER_ID)
        self.resolve_error: Exception | None = None
        self.network_error: Exception | None = None

    def httpx_get(self):
        async def _get(url, *args, **kwargs):
            if self.network_error is not None:
                raise self.network_error
            if self.token_status != 200:
                return SimpleNamespace(status_code=self.token_status, json=lambda: {})
            return SimpleNamespace(
                status_code=200, json=lambda: {"id": self.user_id}
            )

        return AsyncMock(side_effect=_get)

    def resolver(self):
        def _resolve(user_id: str):
            if self.resolve_error is not None:
                raise self.resolve_error
            return self.scope

        return _resolve


@pytest.fixture
def auth_state() -> _AuthState:
    return _AuthState()


@pytest.fixture(params=["modal", "cloud"])
def modal_app(auth_state: _AuthState, request):
    """App instance built in modal mode with all auth backends mocked."""
    from app.core.config import get_settings

    def _fake_reserve(feature: str, idempotency_key: str = "") -> dict:
        # Metering is out of scope for the contract/auth suites: charging
        # would touch Postgres (no DB in unit tests) via commerce.
        return {"provider": "managed", "feature": feature, "plan": "free"}

    settings = get_settings()
    previous_mode = settings.mindmesh_execution_mode
    settings.mindmesh_execution_mode = request.param
    with (
        patch("httpx.AsyncClient.get", new=auth_state.httpx_get()),
        patch("app.core.cloud_auth.resolve_user", new=auth_state.resolver()),
        patch("app.services.commerce.reserve", new=_fake_reserve),
        # Cloud state and vectors are out of scope here: return empty defaults.
        patch(
            "app.services.cloud_db.load",
            new=lambda kind, default: default,
        ),
        patch(
            "app.services.vectorstore.get_client",
            side_effect=ConnectionError("no qdrant in unit tests"),
        ),
    ):
        from app.main import create_app

        app = create_app()
        yield app
    settings.mindmesh_execution_mode = previous_mode


@pytest.fixture
def modal_client(modal_app):
    return TestClient(modal_app)
