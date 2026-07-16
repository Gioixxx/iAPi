import httpx
import respx
from httpx import Response

from tests.conftest import OLLAMA_BASE_URL


async def test_generate_success(api_client):
    with respx.mock:
        respx.post(f"{OLLAMA_BASE_URL}/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "model": "llama3.2:3b",
                    "response": "Hello!",
                    "eval_count": 12,
                    "total_duration": 2_000_000_000,
                },
            )
        )
        resp = await api_client.post("/generate", json={"prompt": "Hi"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Hello!"
    assert body["model"] == "llama3.2:3b"
    assert body["eval_count"] == 12
    assert body["total_duration_ms"] == 2000


async def test_generate_model_not_ready_returns_503(api_client, readiness):
    readiness.model_present = False

    resp = await api_client.post("/generate", json={"prompt": "Hi"})

    assert resp.status_code == 503


async def test_generate_ollama_timeout_returns_504(api_client):
    with respx.mock:
        respx.post(f"{OLLAMA_BASE_URL}/api/generate").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        resp = await api_client.post("/generate", json={"prompt": "Hi"})

    assert resp.status_code == 504


async def test_generate_ollama_unreachable_returns_502(api_client):
    with respx.mock:
        respx.post(f"{OLLAMA_BASE_URL}/api/generate").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        resp = await api_client.post("/generate", json={"prompt": "Hi"})

    assert resp.status_code == 502


async def test_generate_rejects_empty_prompt(api_client):
    resp = await api_client.post("/generate", json={"prompt": ""})

    assert resp.status_code == 422
