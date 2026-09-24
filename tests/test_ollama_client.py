import json

import pytest
import respx
from httpx import Response

from app.ai.base import (
    GenerationResult,
    LLMError,
    LLMModelMissingError,
    LLMUnavailableError,
    TextDelta,
)
from tests.conftest import OLLAMA_BASE_URL, OLLAMA_MODEL

PULL_URL = f"{OLLAMA_BASE_URL}/api/pull"
GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"


async def test_pull_model_yields_progress_percent(ollama_client):
    ndjson = "\n".join(
        [
            '{"status": "pulling manifest"}',
            '{"status": "downloading", "total": 200, "completed": 50}',
            "not json",
            '{"status": "downloading", "total": 200, "completed": 200}',
            '{"status": "success"}',
        ]
    )
    with respx.mock:
        respx.post(PULL_URL).mock(return_value=Response(200, text=ndjson))
        progress = [p async for p in ollama_client.pull_model(OLLAMA_MODEL, timeout=60)]

    assert progress == [None, 25, 100, None]


async def test_pull_model_error_event_raises(ollama_client):
    ndjson = '{"status": "pulling manifest"}\n{"error": "pull model manifest: file does not exist"}'
    with respx.mock:
        respx.post(PULL_URL).mock(return_value=Response(200, text=ndjson))
        with pytest.raises(LLMError, match="file does not exist"):
            [p async for p in ollama_client.pull_model("nope:1b", timeout=60)]


async def test_generate_stream_yields_deltas_then_result(ollama_client):
    ndjson = "\n".join(
        [
            '{"model": "llama3.2:3b", "response": "Ciao", "done": false}',
            '{"model": "llama3.2:3b", "response": " Marco", "done": false}',
            '{"model": "llama3.2:3b", "response": "", "done": true, "eval_count": 2,'
            ' "total_duration": 3000000000}',
        ]
    )
    with respx.mock:
        route = respx.post(GENERATE_URL).mock(return_value=Response(200, text=ndjson))
        events = [e async for e in ollama_client.generate_stream("Hi", OLLAMA_MODEL, system="S")]

    payload = json.loads(route.calls.last.request.content)
    assert payload["stream"] is True
    assert payload["system"] == "S"
    assert events == [
        TextDelta("Ciao"),
        TextDelta(" Marco"),
        GenerationResult(
            text="Ciao Marco", model="llama3.2:3b", eval_count=2, total_duration_ms=3000
        ),
    ]


async def test_generate_stream_error_event_raises(ollama_client):
    ndjson = '{"response": "Ciao", "done": false}\n{"error": "out of memory"}'
    with respx.mock:
        respx.post(GENERATE_URL).mock(return_value=Response(200, text=ndjson))
        with pytest.raises(LLMError, match="out of memory"):
            [e async for e in ollama_client.generate_stream("Hi", OLLAMA_MODEL)]


async def test_generate_stream_without_final_event_raises(ollama_client):
    with respx.mock:
        respx.post(GENERATE_URL).mock(
            return_value=Response(200, text='{"response": "Ciao", "done": false}')
        )
        with pytest.raises(LLMUnavailableError, match="before the final event"):
            [e async for e in ollama_client.generate_stream("Hi", OLLAMA_MODEL)]


async def test_generate_stream_missing_model_raises(ollama_client):
    with respx.mock:
        respx.post(GENERATE_URL).mock(return_value=Response(404, json={"error": "not found"}))
        with pytest.raises(LLMModelMissingError):
            [e async for e in ollama_client.generate_stream("Hi", "nope:1b")]
