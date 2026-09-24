from tests.conftest import LMSTUDIO_MODEL, OLLAMA_MODEL


async def test_health_ready(api_client):
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["provider"] == "ollama"
    assert body["model"] == OLLAMA_MODEL
    assert body["model_present"] is True
    assert body["llm_reachable"] is True
    assert body["ollama_reachable"] is True


async def test_health_pulling_is_still_200(api_client, readiness):
    readiness.status = "pulling"
    readiness.model_present = False
    readiness.pull_progress_percent = 42

    resp = await api_client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pulling"
    assert body["pull_progress_percent"] == 42


async def test_health_unreachable_is_503(api_client, readiness):
    readiness.llm_reachable = False
    readiness.status = "degraded"

    resp = await api_client.get("/health")

    assert resp.status_code == 503


async def test_health_reports_lmstudio_provider(lmstudio_api_client):
    resp = await lmstudio_api_client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "lmstudio"
    assert body["model"] == LMSTUDIO_MODEL
