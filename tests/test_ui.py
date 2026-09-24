async def test_index_serves_the_browser_ui(api_client):
    resp = await api_client.get("/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.headers["cache-control"] == "no-cache"
    # The page calls the API with relative URLs, so it works under any host/port.
    assert 'fetch("generate/stream"' in resp.text
    assert 'fetch("health"' in resp.text


async def test_index_is_not_in_the_openapi_schema(api_client):
    resp = await api_client.get("/openapi.json")

    assert "/" not in resp.json()["paths"]
