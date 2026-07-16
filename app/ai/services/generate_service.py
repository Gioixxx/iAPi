import logging

from fastapi import HTTPException

from app.ai.client import (
    OllamaClient,
    OllamaModelMissingError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from app.core.config import Settings
from app.core.readiness import ModelReadiness
from app.schemas.generate import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class GenerateService:
    def __init__(self, client: OllamaClient, settings: Settings, readiness: ModelReadiness):
        self._client = client
        self._settings = settings
        self._readiness = readiness

    async def generate(self, body: GenerateRequest) -> GenerateResponse:
        if not self._readiness.model_present:
            raise HTTPException(
                status_code=503,
                detail=f"model '{self._settings.ollama_model}' is still pulling, retry shortly",
            )

        try:
            result = await self._client.generate(
                body.prompt,
                self._settings.ollama_model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        except OllamaModelMissingError as exc:
            self._readiness.model_present = False
            self._readiness.status = "pulling"
            raise HTTPException(
                status_code=503,
                detail=(
                    f"model '{self._settings.ollama_model}' is missing on Ollama, "
                    "re-pull triggered"
                ),
            ) from exc
        except OllamaTimeoutError as exc:
            raise HTTPException(status_code=504, detail="Ollama did not respond in time") from exc
        except OllamaUnavailableError as exc:
            raise HTTPException(status_code=502, detail="Ollama is unreachable") from exc

        total_duration_ns = result.get("total_duration")
        return GenerateResponse(
            response=result.get("response", ""),
            model=result.get("model", self._settings.ollama_model),
            eval_count=result.get("eval_count"),
            total_duration_ms=(
                total_duration_ns // 1_000_000 if total_duration_ns is not None else None
            ),
        )
