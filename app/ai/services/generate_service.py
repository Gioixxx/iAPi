import logging
from collections.abc import AsyncGenerator, AsyncIterator

import anyio
from fastapi import HTTPException

from app.ai.base import (
    GenerationResult,
    LLMClient,
    LLMEmptyResponseError,
    LLMError,
    LLMModelMissingError,
    LLMTimeoutError,
    LLMUnavailableError,
    StreamEvent,
    TextDelta,
)
from app.core.config import Settings
from app.core.readiness import ModelReadiness
from app.schemas.generate import (
    GenerateRequest,
    GenerateResponse,
    StreamDelta,
    StreamDone,
    StreamError,
)

logger = logging.getLogger(__name__)


class GenerateService:
    def __init__(self, client: LLMClient, settings: Settings, readiness: ModelReadiness):
        self._client = client
        self._settings = settings
        self._readiness = readiness

    def _require_model(self) -> str:
        model = self._settings.llm_model
        if not self._readiness.model_present:
            raise HTTPException(
                status_code=503,
                detail=f"model '{model}' is still pulling, retry shortly",
            )
        return model

    def _http_error(self, exc: LLMError) -> HTTPException:
        model = self._settings.llm_model
        provider = self._settings.llm_provider
        if isinstance(exc, LLMModelMissingError):
            self._readiness.model_present = False
            self._readiness.status = "pulling"
            return HTTPException(
                status_code=503,
                detail=f"model '{model}' is missing on {provider}, re-pull triggered",
            )
        if isinstance(exc, LLMEmptyResponseError):
            return HTTPException(status_code=502, detail=str(exc))
        if isinstance(exc, LLMTimeoutError):
            return HTTPException(status_code=504, detail=f"{provider} did not respond in time")
        if isinstance(exc, LLMUnavailableError):
            return HTTPException(status_code=502, detail=f"{provider} is unreachable")
        return HTTPException(status_code=502, detail=str(exc))

    async def generate(self, body: GenerateRequest) -> GenerateResponse:
        model = self._require_model()
        try:
            result = await self._client.generate(
                body.prompt,
                model,
                system=body.system,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        except LLMError as exc:
            raise self._http_error(exc) from exc

        return GenerateResponse(
            response=result.text,
            model=result.model,
            eval_count=result.eval_count,
            total_duration_ms=result.total_duration_ms,
        )

    async def open_stream(self, body: GenerateRequest) -> AsyncIterator[str]:
        """Starts the generation and waits for its first event before returning, so that a
        backend that is down or lacks the model still gets a real HTTP status (502/503)
        instead of a 200 whose only line is an error."""
        model = self._require_model()
        events = self._client.generate_stream(
            body.prompt,
            model,
            system=body.system,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        try:
            first = await anext(events)
        except LLMError as exc:
            raise self._http_error(exc) from exc
        except StopAsyncIteration as exc:
            raise HTTPException(status_code=502, detail="empty stream from backend") from exc
        return self._ndjson(first, events)

    async def _ndjson(
        self, first: StreamEvent, events: AsyncGenerator[StreamEvent, None]
    ) -> AsyncIterator[str]:
        try:
            yield self._encode(first)
            if isinstance(first, GenerationResult):
                return
            async for event in events:
                yield self._encode(event)
        except LLMError as exc:
            error = self._http_error(exc)
            yield (
                StreamError(status=error.status_code, detail=error.detail).model_dump_json() + "\n"
            )
        finally:
            # A client that disconnects cancels this generator; without the shield the
            # cancellation would also interrupt aclose() and leave the backend generating.
            with anyio.CancelScope(shield=True):
                await events.aclose()

    @staticmethod
    def _encode(event: StreamEvent) -> str:
        if isinstance(event, TextDelta):
            line = StreamDelta(text=event.text)
        else:
            line = StreamDone(
                response=event.text,
                model=event.model,
                eval_count=event.eval_count,
                total_duration_ms=event.total_duration_ms,
            )
        return line.model_dump_json() + "\n"
