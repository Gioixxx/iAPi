import json

import httpx
import respx
from httpx import Response

from tests.conftest import LMSTUDIO_BASE_URL, LMSTUDIO_MODEL, OLLAMA_BASE_URL


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


async def test_generate_forwards_system_prompt_to_ollama(api_client):
    with respx.mock:
        route = respx.post(f"{OLLAMA_BASE_URL}/api/generate").mock(
            return_value=Response(200, json={"model": "llama3.2:3b", "response": "Ciao Marco,"})
        )
        resp = await api_client.post(
            "/generate", json={"prompt": "Scrivi a Marco", "system": "Scrivi email brevi."}
        )

    assert resp.status_code == 200
    payload = json.loads(route.calls.last.request.content)
    assert payload["system"] == "Scrivi email brevi."
    assert payload["prompt"] == "Scrivi a Marco"


async def test_generate_via_lmstudio(lmstudio_api_client):
    completion = {
        "model": LMSTUDIO_MODEL,
        "choices": [{"message": {"content": "Ciao Marco,"}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 9},
    }
    with respx.mock:
        respx.post(f"{LMSTUDIO_BASE_URL}/v1/chat/completions").mock(
            return_value=Response(200, json=completion)
        )
        resp = await lmstudio_api_client.post(
            "/generate", json={"prompt": "Scrivi a Marco", "system": "Scrivi email brevi."}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Ciao Marco,"
    assert body["model"] == LMSTUDIO_MODEL
    assert body["eval_count"] == 9
    assert body["total_duration_ms"] is not None


async def test_generate_lmstudio_reasoning_starved_returns_502(lmstudio_api_client):
    starved = {
        "model": LMSTUDIO_MODEL,
        "choices": [
            {
                "message": {"content": "", "reasoning_content": "Okay, the user"},
                "finish_reason": "length",
            }
        ],
    }
    with respx.mock:
        respx.post(f"{LMSTUDIO_BASE_URL}/v1/chat/completions").mock(
            return_value=Response(200, json=starved)
        )
        resp = await lmstudio_api_client.post("/generate", json={"prompt": "Hi", "max_tokens": 5})

    assert resp.status_code == 502
    assert "max_tokens" in resp.json()["detail"]


async def test_generate_lmstudio_unreachable_names_provider(lmstudio_api_client):
    with respx.mock:
        respx.post(f"{LMSTUDIO_BASE_URL}/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        resp = await lmstudio_api_client.post("/generate", json={"prompt": "Hi"})

    assert resp.status_code == 502
    assert resp.json()["detail"] == "lmstudio is unreachable"


async def test_generate_rejects_empty_system(api_client):
    resp = await api_client.post("/generate", json={"prompt": "Hi", "system": ""})

    assert resp.status_code == 422
