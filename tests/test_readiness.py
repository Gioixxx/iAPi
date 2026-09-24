import asyncio

import respx
from httpx import Response

from app.core.readiness import ModelReadiness, bootstrap_model
from tests.conftest import LMSTUDIO_BASE_URL, LMSTUDIO_MODEL, make_settings


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), timeout)


async def test_bootstrap_downloads_missing_lmstudio_model_then_is_ready(lmstudio_client):
    settings = make_settings(llm_provider="lmstudio", readiness_recheck_seconds=60)
    readiness = ModelReadiness()
    listed = {"models": [{"key": LMSTUDIO_MODEL, "variants": []}]}

    with respx.mock:
        respx.get(f"{LMSTUDIO_BASE_URL}/api/v1/models").mock(
            side_effect=[Response(200, json={"models": []}), Response(200, json=listed)]
        )
        download = respx.post(f"{LMSTUDIO_BASE_URL}/api/v1/models/download").mock(
            return_value=Response(200, json={"status": "already_downloaded"})
        )
        task = asyncio.create_task(bootstrap_model(lmstudio_client, settings, readiness))
        try:
            await _wait_for(lambda: readiness.status == "ready" and download.called)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert readiness.llm_reachable is True
    assert readiness.model_present is True


async def test_bootstrap_unreachable_backend_is_degraded(lmstudio_client):
    settings = make_settings(llm_provider="lmstudio", pull_retry_backoff_seconds=60)
    readiness = ModelReadiness()

    with respx.mock:
        respx.get(f"{LMSTUDIO_BASE_URL}/api/v1/models").mock(return_value=Response(503))
        task = asyncio.create_task(bootstrap_model(lmstudio_client, settings, readiness))
        try:
            await _wait_for(lambda: readiness.status == "degraded")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert readiness.llm_reachable is False
