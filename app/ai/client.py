import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base class for errors raised by OllamaClient."""


class OllamaUnavailableError(OllamaError):
    """Ollama could not be reached (connection refused, DNS failure, etc.)."""


class OllamaModelMissingError(OllamaError):
    """Ollama is reachable but does not have the requested model pulled."""


class OllamaTimeoutError(OllamaError):
    """Ollama was reachable but did not respond within the configured timeout."""


def _normalize_tag(model: str) -> str:
    """Ollama tags default to ':latest' — normalize so 'llama3.2:3b' == 'llama3.2:3b' and
    bare names implicitly compare against the ':latest' tag Ollama itself assumes."""
    return model if ":" in model else f"{model}:latest"


class OllamaClient:
    def __init__(self, base_url: str, connect_timeout: float, request_timeout: float):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=connect_timeout, read=request_timeout, write=10, pool=5),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def list_models(self) -> list[str]:
        try:
            resp = await self._http.get("/api/tags")
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(str(exc)) from exc
        return [m["name"] for m in resp.json().get("models", [])]

    async def is_model_present(self, model: str) -> bool:
        target = _normalize_tag(model)
        return target in {_normalize_tag(name) for name in await self.list_models()}

    async def pull_model(self, model: str, timeout: float) -> AsyncIterator[dict[str, Any]]:
        """Streams NDJSON progress events from POST /api/pull. Raises OllamaUnavailableError
        if the connection itself fails; individual malformed lines are skipped."""
        try:
            async with self._http.stream(
                "POST", "/api/pull", json={"model": model, "stream": True}, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("skipping malformed pull progress line: %r", line)
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(str(exc)) from exc

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if options:
            payload["options"] = options

        try:
            resp = await self._http.post("/api/generate", json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(str(exc)) from exc

        if resp.status_code == 404:
            raise OllamaModelMissingError(f"model not found: {model}")
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OllamaUnavailableError(str(exc)) from exc

        return resp.json()
