import pytest
import respx
from httpx import Response

from app.ai.base import LLMError
from tests.conftest import OLLAMA_BASE_URL, OLLAMA_MODEL

PULL_URL = f"{OLLAMA_BASE_URL}/api/pull"


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
