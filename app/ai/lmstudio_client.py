import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import httpx

from app.ai.base import (
    GenerationResult,
    LLMEmptyResponseError,
    LLMError,
    LLMModelMissingError,
    LLMTimeoutError,
    LLMUnavailableError,
    StreamEvent,
    TextDelta,
)

logger = logging.getLogger(__name__)

_DOWNLOAD_DONE = {"completed", "already_downloaded"}


def _error_detail(resp: httpx.Response) -> dict[str, Any]:
    """LM Studio wraps errors as {"error": {"message", "type", "param"}}; anything else
    (plain-text body, proxy HTML page) yields an empty dict."""
    try:
        error = resp.json().get("error")
    except ValueError:
        return {}
    return error if isinstance(error, dict) else {}


def _download_percent(status: dict[str, Any]) -> int | None:
    total = status.get("total_size_bytes")
    downloaded = status.get("downloaded_bytes")
    if not total or downloaded is None:
        return None
    return round(downloaded / total * 100)


class LMStudioClient:
    """Talks to LM Studio / llmster (>= 0.4.0): the OpenAI-compatible /v1 surface for
    generation, the native /api/v1 surface for model presence and download — /v1 has
    neither, and /v1/models lists downloaded models only when JIT loading is enabled."""

    def __init__(
        self,
        base_url: str,
        connect_timeout: float,
        request_timeout: float,
        *,
        api_token: str | None = None,
        reasoning_effort: str | None = None,
        download_poll_seconds: float = 2.0,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_token}"} if api_token else None,
            timeout=httpx.Timeout(connect=connect_timeout, read=request_timeout, write=10, pool=5),
        )
        self._reasoning_effort = reasoning_effort
        self._download_poll_seconds = download_poll_seconds

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._http.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = _error_detail(resp).get("message") or str(exc)
            raise LLMUnavailableError(message) from exc

    async def list_models(self) -> list[dict[str, Any]]:
        resp = await self._send("GET", "/api/v1/models")
        self._raise_for_status(resp)
        return resp.json().get("models", [])

    async def is_model_present(self, model: str) -> bool:
        return any(
            model == entry.get("key") or model in entry.get("variants", [])
            for entry in await self.list_models()
        )

    async def pull_model(self, model: str, timeout: float) -> AsyncIterator[int | None]:
        """Starts a download job and polls it until done, yielding progress percent. The
        download runs inside LM Studio: cancelling this iterator, or hitting `timeout`,
        stops the polling, not the download itself."""
        resp = await self._send("POST", "/api/v1/models/download", json={"model": model})
        if resp.status_code == 404:
            raise LLMModelMissingError(
                _error_detail(resp).get("message") or f"model not found: {model}"
            )
        self._raise_for_status(resp)
        status = resp.json()
        job_id = status.get("job_id")
        deadline = time.monotonic() + timeout

        while status.get("status") not in _DOWNLOAD_DONE:
            if status.get("status") == "failed":
                raise LLMError(f"LM Studio could not download '{model}'")
            if not job_id:
                raise LLMError(f"LM Studio returned no job id for the download of '{model}'")
            yield _download_percent(status)
            if time.monotonic() >= deadline:
                raise LLMTimeoutError(f"download of '{model}' still running after {timeout}s")
            await asyncio.sleep(self._download_poll_seconds)
            resp = await self._send("GET", f"/api/v1/models/download/status/{job_id}")
            self._raise_for_status(resp)
            status = resp.json()

    def _chat_payload(
        self,
        prompt: str,
        model: str,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        if system is not None:
            messages.insert(0, {"role": "system", "content": system})

        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if stream:
            # Without it the OpenAI stream carries no token counts.
            payload["stream_options"] = {"include_usage": True}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    def _check_chat_status(self, resp: httpx.Response, model: str) -> None:
        if resp.status_code == 400 and _error_detail(resp).get("param") == "model":
            raise LLMModelMissingError(f"model not available on LM Studio: {model}")
        self._raise_for_status(resp)

    @staticmethod
    def _reasoning_starved(model: str) -> LLMEmptyResponseError:
        return LLMEmptyResponseError(
            f"'{model}' spent the whole max_tokens budget reasoning and wrote no answer: "
            "raise max_tokens or disable reasoning (LMSTUDIO_REASONING_EFFORT=none)"
        )

    @staticmethod
    def _served_model(served: str | None, requested: str) -> str:
        # With a single model loaded, LM Studio answers with it even when the request names
        # another one — surface the substitution instead of reporting the requested name.
        served = served or requested
        if served != requested:
            logger.warning("LM Studio served %r instead of the requested %r", served, requested)
        return served

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        payload = self._chat_payload(prompt, model, system, temperature, max_tokens, stream=False)

        started = time.perf_counter()
        resp = await self._send("POST", "/v1/chat/completions", json=payload)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        self._check_chat_status(resp, model)

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMUnavailableError("LM Studio returned a completion without choices")
        choice = choices[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        if (
            not text
            and choice.get("finish_reason") == "length"
            and message.get("reasoning_content")
        ):
            raise self._reasoning_starved(model)

        usage = data.get("usage") or {}
        return GenerationResult(
            text=text,
            model=self._served_model(data.get("model"), model),
            eval_count=usage.get("completion_tokens"),
            total_duration_ms=elapsed_ms,
        )

    async def generate_stream(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Parses the SSE stream of /v1/chat/completions: `data: {chunk}` lines, a chunk with
        the finish_reason, one with `usage` and empty choices, then `data: [DONE]`."""
        payload = self._chat_payload(prompt, model, system, temperature, max_tokens, stream=True)
        parts: list[str] = []
        reasoned = False
        finish_reason: str | None = None
        served: str | None = None
        usage: dict[str, Any] = {}

        started = time.perf_counter()
        try:
            async with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
                if resp.is_error:
                    await resp.aread()
                    self._check_chat_status(resp, model)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("skipping malformed stream line: %r", line)
                        continue
                    served = chunk.get("model") or served
                    usage = chunk.get("usage") or usage
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        reasoned = reasoned or bool(delta.get("reasoning_content"))
                        finish_reason = choice.get("finish_reason") or finish_reason
                        if text := delta.get("content"):
                            parts.append(text)
                            yield TextDelta(text)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc

        if not parts and finish_reason == "length" and reasoned:
            raise self._reasoning_starved(model)
        yield GenerationResult(
            text="".join(parts),
            model=self._served_model(served, model),
            eval_count=usage.get("completion_tokens"),
            total_duration_ms=round((time.perf_counter() - started) * 1000),
        )
