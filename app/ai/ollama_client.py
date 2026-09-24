import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.base import (
    GenerationResult,
    LLMError,
    LLMModelMissingError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)


def _normalize_tag(model: str) -> str:
    """Ollama tags default to ':latest' — normalize so 'llama3.2:3b' == 'llama3.2:3b' and
    bare names implicitly compare against the ':latest' tag Ollama itself assumes."""
    return model if ":" in model else f"{model}:latest"


def _progress_percent(event: dict[str, Any]) -> int | None:
    total = event.get("total")
    completed = event.get("completed")
    if not total:
        return None
    return round(completed / total * 100) if completed is not None else None


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
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        return [m["name"] for m in resp.json().get("models", [])]

    async def is_model_present(self, model: str) -> bool:
        target = _normalize_tag(model)
        return target in {_normalize_tag(name) for name in await self.list_models()}

    async def pull_model(self, model: str, timeout: float) -> AsyncIterator[int | None]:
        """Streams NDJSON progress events from POST /api/pull, yielding progress percent.
        Raises LLMUnavailableError if the connection itself fails and LLMError if Ollama
        reports a pull error in-stream; individual malformed lines are skipped."""
        try:
            async with self._http.stream(
                "POST", "/api/pull", json={"model": model, "stream": True}, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("skipping malformed pull progress line: %r", line)
                        continue
                    if "error" in event:
                        raise LLMError(f"Ollama could not pull '{model}': {event['error']}")
                    yield _progress_percent(event)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if system is not None:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            resp = await self._http.post("/api/generate", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc

        if resp.status_code == 404:
            raise LLMModelMissingError(f"model not found: {model}")
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(str(exc)) from exc

        data = resp.json()
        total_duration_ns = data.get("total_duration")
        return GenerationResult(
            text=data.get("response", ""),
            model=data.get("model", model),
            eval_count=data.get("eval_count"),
            total_duration_ms=(
                total_duration_ns // 1_000_000 if total_duration_ns is not None else None
            ),
        )
