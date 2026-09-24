import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from app.ai.base import LLMClient, LLMTimeoutError, LLMUnavailableError
from app.core.config import Settings

logger = logging.getLogger(__name__)

ReadinessStatus = Literal["starting", "pulling", "ready", "degraded", "error"]


@dataclass
class ModelReadiness:
    status: ReadinessStatus = "starting"
    llm_reachable: bool = False
    model_present: bool = False
    pull_progress_percent: int | None = None


def _backend_url(settings: Settings) -> str:
    if settings.llm_provider == "lmstudio":
        return settings.lmstudio_base_url
    return settings.ollama_base_url


async def bootstrap_model(client: LLMClient, settings: Settings, readiness: ModelReadiness) -> None:
    """Runs forever as a background task started from the FastAPI lifespan. Never blocks
    startup: `docker compose up -d` must return quickly regardless of how long the model
    pull takes (pi-deploy's SSH exec for that command has a hard 60s timeout). Also
    self-heals: keeps re-checking after reaching 'ready' so a reset volume or a recreated
    backend container gets the model re-pulled automatically, with no manual SSH step."""
    model = settings.llm_model
    while True:
        try:
            if await client.is_model_present(model):
                readiness.status = "ready"
                readiness.llm_reachable = True
                readiness.model_present = True
                readiness.pull_progress_percent = None
                await asyncio.sleep(settings.readiness_recheck_seconds)
                continue

            readiness.status = "pulling"
            readiness.llm_reachable = True
            readiness.model_present = False
            async for percent in client.pull_model(
                model, timeout=settings.ollama_pull_timeout_seconds
            ):
                readiness.pull_progress_percent = percent

            readiness.status = "ready"
            readiness.model_present = True
            readiness.pull_progress_percent = None
        except (LLMUnavailableError, LLMTimeoutError) as exc:
            # Logged on the transition only: an unreachable backend retries every
            # pull_retry_backoff_seconds and would otherwise flood the log.
            if readiness.status != "degraded":
                logger.warning(
                    "%s unreachable at %s: %s: %s",
                    settings.llm_provider,
                    _backend_url(settings),
                    type(exc.__cause__ or exc).__name__,
                    exc,
                )
            readiness.status = "degraded"
            readiness.llm_reachable = False
            await asyncio.sleep(settings.pull_retry_backoff_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            readiness.status = "error"
            logger.exception("model bootstrap failed, retrying")
            await asyncio.sleep(settings.pull_retry_backoff_seconds)
