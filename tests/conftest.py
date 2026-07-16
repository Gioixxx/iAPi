import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.client import OllamaClient
from app.api.deps import get_ollama_client, get_readiness
from app.core.readiness import ModelReadiness
from app.main import app

OLLAMA_BASE_URL = "http://test-ollama:11434"


@pytest.fixture
async def ollama_client():
    client = OllamaClient(base_url=OLLAMA_BASE_URL, connect_timeout=5, request_timeout=10)
    yield client
    await client.aclose()


@pytest.fixture
def readiness():
    return ModelReadiness(status="ready", ollama_reachable=True, model_present=True)


@pytest.fixture
async def api_client(ollama_client, readiness):
    """AsyncClient talking to the app over ASGI, with the Ollama-facing dependencies
    overridden — bypasses the real lifespan entirely (no background bootstrap task, no
    network dependency), so tests control readiness/Ollama responses directly."""
    app.dependency_overrides[get_ollama_client] = lambda: ollama_client
    app.dependency_overrides[get_readiness] = lambda: readiness
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
