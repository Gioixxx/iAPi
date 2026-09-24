import json

import httpx
import pytest
import respx
from httpx import Response

from app.ai.base import (
    GenerationResult,
    LLMEmptyResponseError,
    LLMError,
    LLMModelMissingError,
    LLMTimeoutError,
    LLMUnavailableError,
    TextDelta,
)
from app.ai.lmstudio_client import LMStudioClient
from tests.conftest import LMSTUDIO_BASE_URL, LMSTUDIO_MODEL

CHAT_URL = f"{LMSTUDIO_BASE_URL}/v1/chat/completions"
MODELS_URL = f"{LMSTUDIO_BASE_URL}/api/v1/models"
DOWNLOAD_URL = f"{LMSTUDIO_BASE_URL}/api/v1/models/download"


def _completion(content: str, *, finish_reason: str = "stop", **message_extra) -> dict:
    return {
        "model": LMSTUDIO_MODEL,
        "choices": [
            {
                "message": {"role": "assistant", "content": content, **message_extra},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 42, "total_tokens": 62},
    }


async def test_is_model_present_matches_key_and_variant(lmstudio_client):
    models = {
        "models": [
            {"key": "google/gemma-4-e2b", "variants": ["google/gemma-4-e2b@q4_k_m"]},
        ]
    }
    with respx.mock:
        respx.get(MODELS_URL).mock(return_value=Response(200, json=models))
        assert await lmstudio_client.is_model_present("google/gemma-4-e2b")
        assert await lmstudio_client.is_model_present("google/gemma-4-e2b@q4_k_m")
        assert not await lmstudio_client.is_model_present("qwen/qwen3-4b")


async def test_is_model_present_unreachable_raises(lmstudio_client):
    with respx.mock:
        respx.get(MODELS_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        with pytest.raises(LLMUnavailableError):
            await lmstudio_client.is_model_present(LMSTUDIO_MODEL)


async def test_pull_model_already_downloaded_yields_nothing(lmstudio_client):
    with respx.mock:
        respx.post(DOWNLOAD_URL).mock(
            return_value=Response(200, json={"status": "already_downloaded"})
        )
        progress = [p async for p in lmstudio_client.pull_model(LMSTUDIO_MODEL, timeout=60)]

    assert progress == []


async def test_pull_model_polls_job_until_completed(lmstudio_client):
    with respx.mock:
        start = respx.post(DOWNLOAD_URL).mock(
            return_value=Response(
                200, json={"job_id": "job_1", "status": "downloading", "total_size_bytes": 200}
            )
        )
        respx.get(f"{DOWNLOAD_URL}/status/job_1").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "job_id": "job_1",
                        "status": "downloading",
                        "total_size_bytes": 200,
                        "downloaded_bytes": 100,
                    },
                ),
                Response(
                    200,
                    json={
                        "job_id": "job_1",
                        "status": "completed",
                        "total_size_bytes": 200,
                        "downloaded_bytes": 200,
                    },
                ),
            ]
        )
        progress = [p async for p in lmstudio_client.pull_model(LMSTUDIO_MODEL, timeout=60)]

    assert json.loads(start.calls.last.request.content) == {"model": LMSTUDIO_MODEL}
    assert progress == [None, 50]


async def test_pull_model_failed_job_raises(lmstudio_client):
    with respx.mock:
        respx.post(DOWNLOAD_URL).mock(
            return_value=Response(200, json={"job_id": "job_1", "status": "downloading"})
        )
        respx.get(f"{DOWNLOAD_URL}/status/job_1").mock(
            return_value=Response(200, json={"job_id": "job_1", "status": "failed"})
        )
        with pytest.raises(LLMError, match="could not download"):
            [p async for p in lmstudio_client.pull_model(LMSTUDIO_MODEL, timeout=60)]


async def test_pull_model_times_out_while_job_is_running(lmstudio_client):
    with respx.mock:
        respx.post(DOWNLOAD_URL).mock(
            return_value=Response(200, json={"job_id": "job_1", "status": "downloading"})
        )
        with pytest.raises(LLMTimeoutError):
            [p async for p in lmstudio_client.pull_model(LMSTUDIO_MODEL, timeout=0)]


async def test_pull_model_unknown_model_raises_missing(lmstudio_client):
    with respx.mock:
        respx.post(DOWNLOAD_URL).mock(
            return_value=Response(
                404,
                json={"error": {"message": "x/y not found", "type": "model_not_found"}},
            )
        )
        with pytest.raises(LLMModelMissingError, match="x/y not found"):
            [p async for p in lmstudio_client.pull_model("x/y", timeout=60)]


async def test_generate_sends_chat_payload_and_maps_result(lmstudio_client):
    with respx.mock:
        route = respx.post(CHAT_URL).mock(
            return_value=Response(200, json=_completion("Ciao Marco,"))
        )
        result = await lmstudio_client.generate(
            "Scrivi a Marco",
            LMSTUDIO_MODEL,
            system="Scrivi email brevi.",
            temperature=0.7,
            max_tokens=300,
        )

    payload = json.loads(route.calls.last.request.content)
    assert payload == {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": "Scrivi email brevi."},
            {"role": "user", "content": "Scrivi a Marco"},
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 300,
        "reasoning_effort": "none",
    }
    assert result.text == "Ciao Marco,"
    assert result.model == LMSTUDIO_MODEL
    assert result.eval_count == 42
    assert result.total_duration_ms is not None


async def test_generate_omits_reasoning_effort_when_not_configured():
    client = LMStudioClient(base_url=LMSTUDIO_BASE_URL, connect_timeout=5, request_timeout=10)
    try:
        with respx.mock:
            route = respx.post(CHAT_URL).mock(return_value=Response(200, json=_completion("ok")))
            await client.generate("Hi", LMSTUDIO_MODEL)
    finally:
        await client.aclose()

    payload = json.loads(route.calls.last.request.content)
    assert "reasoning_effort" not in payload
    assert payload["messages"] == [{"role": "user", "content": "Hi"}]


async def test_generate_sends_api_token_as_bearer():
    client = LMStudioClient(
        base_url=LMSTUDIO_BASE_URL, connect_timeout=5, request_timeout=10, api_token="s3cret"
    )
    try:
        with respx.mock:
            route = respx.post(CHAT_URL).mock(return_value=Response(200, json=_completion("ok")))
            await client.generate("Hi", LMSTUDIO_MODEL)
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Authorization"] == "Bearer s3cret"


async def test_generate_reasoning_starved_raises_empty_response(lmstudio_client):
    starved = _completion("", finish_reason="length", reasoning_content="Okay, the user")
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(200, json=starved))
        with pytest.raises(LLMEmptyResponseError, match="max_tokens"):
            await lmstudio_client.generate("Hi", LMSTUDIO_MODEL, max_tokens=5)


async def test_generate_reports_substituted_model(lmstudio_client):
    substituted = {**_completion("ok"), "model": "qwen/qwen3-0.6b"}
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(200, json=substituted))
        result = await lmstudio_client.generate("Hi", LMSTUDIO_MODEL)

    assert result.model == "qwen/qwen3-0.6b"


async def test_generate_unknown_model_raises_missing(lmstudio_client):
    error = {
        "error": {"message": "No models loaded.", "type": "invalid_request_error", "param": "model"}
    }
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(400, json=error))
        with pytest.raises(LLMModelMissingError):
            await lmstudio_client.generate("Hi", LMSTUDIO_MODEL)


async def test_generate_server_error_raises_unavailable(lmstudio_client):
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(500, text="boom"))
        with pytest.raises(LLMUnavailableError):
            await lmstudio_client.generate("Hi", LMSTUDIO_MODEL)


async def test_generate_timeout_raises(lmstudio_client):
    with respx.mock:
        respx.post(CHAT_URL).mock(side_effect=httpx.ReadTimeout("timed out"))
        with pytest.raises(LLMTimeoutError):
            await lmstudio_client.generate("Hi", LMSTUDIO_MODEL)


def _sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def _chunk(content: str | None = None, *, finish_reason=None, **delta_extra) -> dict:
    delta = {**delta_extra}
    if content is not None:
        delta["content"] = content
    return {
        "model": LMSTUDIO_MODEL,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


async def test_generate_stream_yields_deltas_then_result(lmstudio_client):
    body = _sse(
        _chunk("Ciao", role="assistant"),
        _chunk(" Marco"),
        _chunk(finish_reason="stop"),
        {"model": LMSTUDIO_MODEL, "choices": [], "usage": {"completion_tokens": 7}},
    )
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=Response(200, content=body))
        events = [
            e
            async for e in lmstudio_client.generate_stream(
                "Hi", LMSTUDIO_MODEL, system="Sii breve."
            )
        ]

    payload = json.loads(route.calls.last.request.content)
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["messages"][0] == {"role": "system", "content": "Sii breve."}
    assert events[:2] == [TextDelta("Ciao"), TextDelta(" Marco")]
    result = events[2]
    assert isinstance(result, GenerationResult)
    assert result.text == "Ciao Marco"
    assert result.model == LMSTUDIO_MODEL
    assert result.eval_count == 7
    assert result.total_duration_ms is not None
    assert len(events) == 3


async def test_generate_stream_reasoning_starved_raises(lmstudio_client):
    body = _sse(
        _chunk(reasoning_content="Okay, the user"),
        _chunk(finish_reason="length"),
    )
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(200, content=body))
        with pytest.raises(LLMEmptyResponseError, match="max_tokens"):
            [e async for e in lmstudio_client.generate_stream("Hi", LMSTUDIO_MODEL)]


async def test_generate_stream_unknown_model_raises_missing(lmstudio_client):
    error = {"error": {"message": "No models loaded.", "param": "model"}}
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(400, json=error))
        with pytest.raises(LLMModelMissingError):
            [e async for e in lmstudio_client.generate_stream("Hi", LMSTUDIO_MODEL)]


async def test_generate_stream_unreachable_raises(lmstudio_client):
    with respx.mock:
        respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        with pytest.raises(LLMUnavailableError):
            [e async for e in lmstudio_client.generate_stream("Hi", LMSTUDIO_MODEL)]
