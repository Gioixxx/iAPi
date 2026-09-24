import logging

from fastapi import HTTPException

from app.ai.base import (
    LLMClient,
    LLMEmptyResponseError,
    LLMModelMissingError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.core.config import Settings
from app.core.readiness import ModelReadiness
from app.schemas.generate import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class GenerateService:
    def __init__(self, client: LLMClient, settings: Settings, readiness: ModelReadiness):
        self._client = client
        self._settings = settings
        self._readiness = readiness

    async def generate(self, body: GenerateRequest) -> GenerateResponse:
        model = self._settings.llm_model
        provider = self._settings.llm_provider
        if not self._readiness.model_present:
            raise HTTPException(
                status_code=503,
                detail=f"model '{model}' is still pulling, retry shortly",
            )

        try:
            result = await self._client.generate(
                body.prompt,
                model,
                system=body.system,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        except LLMModelMissingError as exc:
            self._readiness.model_present = False
            self._readiness.status = "pulling"
            raise HTTPException(
                status_code=503,
                detail=f"model '{model}' is missing on {provider}, re-pull triggered",
            ) from exc
        except LLMEmptyResponseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except LLMTimeoutError as exc:
            raise HTTPException(
                status_code=504, detail=f"{provider} did not respond in time"
            ) from exc
        except LLMUnavailableError as exc:
            raise HTTPException(status_code=502, detail=f"{provider} is unreachable") from exc

        return GenerateResponse(
            response=result.text,
            model=result.model,
            eval_count=result.eval_count,
            total_duration_ms=result.total_duration_ms,
        )
