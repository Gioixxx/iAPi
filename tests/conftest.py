from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.base import LLMClient
from app.ai.lmstudio_client import LMStudioClient
from app.ai.ollama_client import OllamaClient
from app.api.deps import get_llm_client, get_readiness, get_settings
from app.core.config import Settings
from app.core.readiness import ModelReadiness
from app.main import app

OLLAMA_BASE_URL = "http://test-ollama:11434"
OLLAMA_MODEL = "llama3.2:3b"
LMSTUDIO_BASE_URL = "http://test-lmstudio:1234"
LMSTUDIO_MODEL = "google/gemma-4-e2b"


def make_settings(**overrides) -> Settings:
    """Settings pinned to known values: no .env file, and every field a test depends on set
    explicitly so a developer's own LLM_PROVIDER/OLLAMA_MODEL env vars can't leak in."""
    values = {
        "llm_provider": "ollama",
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "lmstudio_base_url": LMSTUDIO_BASE_URL,
        "lmstudio_model": LMSTUDIO_MODEL,
        "lmstudio_api_token": None,
        "lmstudio_reasoning_effort": "none",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
async def ollama_client():
    client = OllamaClient(base_url=OLLAMA_BASE_URL, connect_timeout=5, request_timeout=10)
    yield client
    await client.aclose()


@pytest.fixture
async def lmstudio_client():
    client = LMStudioClient(
        base_url=LMSTUDIO_BASE_URL,
        connect_timeout=5,
        request_timeout=10,
        reasoning_effort="none",
        download_poll_seconds=0,
    )
    yield client
    await client.aclose()


@pytest.fixture
def readiness():
    return ModelReadiness(status="ready", llm_reachable=True, model_present=True)


@asynccontextmanager
async def _serve(
    client: LLMClient, settings: Settings, readiness: ModelReadiness
) -> AsyncIterator[AsyncClient]:
    """AsyncClient talking to the app over ASGI, with the backend-facing dependencies
    overridden — bypasses the real lifespan entirely (no background bootstrap task, no
    network dependency), so tests control readiness/backend responses directly."""
    app.dependency_overrides[get_llm_client] = lambda: client
    app.dependency_overrides[get_readiness] = lambda: readiness
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def api_client(ollama_client, readiness):
    async with _serve(ollama_client, make_settings(), readiness) as http:
        yield http


@pytest.fixture
async def lmstudio_api_client(lmstudio_client, readiness):
    async with _serve(lmstudio_client, make_settings(llm_provider="lmstudio"), readiness) as http:
        yield http
