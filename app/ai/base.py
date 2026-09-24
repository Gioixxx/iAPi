from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """Base class for errors raised by the LLM backend clients."""


class LLMUnavailableError(LLMError):
    """The backend could not be reached (connection refused, DNS failure, HTTP error)."""


class LLMModelMissingError(LLMError):
    """The backend is reachable but does not have (or cannot fetch) the requested model."""


class LLMTimeoutError(LLMError):
    """The backend was reachable but did not respond within the configured timeout."""


class LLMEmptyResponseError(LLMError):
    """The backend answered with no text at all. On the OpenAI transport this is a reasoning
    model that spent the whole max_tokens budget thinking: reasoning tokens count against it,
    so the reply comes back empty with finish_reason 'length' instead of failing loudly."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    eval_count: int | None = None
    total_duration_ms: int | None = None


@dataclass(frozen=True)
class TextDelta:
    """A piece of generated text, as soon as the backend produces it."""

    text: str


# What generate_stream yields: any number of TextDelta, then exactly one GenerationResult
# carrying the full text and the stats — or an LLMError raised instead of the result.
StreamEvent = TextDelta | GenerationResult


class LLMClient(Protocol):
    """What the gateway needs from a backend. Implementations translate their own API and
    error shapes into these types, so readiness and services never see provider details."""

    async def aclose(self) -> None: ...

    async def is_model_present(self, model: str) -> bool: ...

    def pull_model(self, model: str, timeout: float) -> AsyncIterator[int | None]:
        """Fetches the model onto the backend, yielding progress percent (None if unknown)."""
        ...

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult: ...

    def generate_stream(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Same request as generate(), streamed. Closing the iterator early closes the
        connection to the backend, which stops the generation there too."""
        ...
