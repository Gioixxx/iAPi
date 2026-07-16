import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from app.ai.client import OllamaClient, OllamaTimeoutError, OllamaUnavailableError
from app.core.config import Settings

logger = logging.getLogger(__name__)

ReadinessStatus = Literal["starting", "pulling", "ready", "degraded", "error"]


@dataclass
class ModelReadiness:
    status: ReadinessStatus = "starting"
    ollama_reachable: bool = False
    model_present: bool = False
    pull_progress_percent: int | None = None


def _progress_percent(event: dict) -> int | None:
    total = event.get("total")
    completed = event.get("completed")
    if not total:
        return None
    return round(completed / total * 100) if completed is not None else None


async def bootstrap_model(
    client: OllamaClient, settings: Settings, readiness: ModelReadiness
) -> None:
    """Runs forever as a background task started from the FastAPI lifespan. Never blocks
    startup: `docker compose up -d` must return quickly regardless of how long the model
    pull takes (pi-deploy's SSH exec for that command has a hard 60s timeout). Also
    self-heals: keeps re-checking after reaching 'ready' so a reset volume or a recreated
    ollama container gets the model re-pulled automatically, with no manual SSH step."""
    while True:
        try:
            if await client.is_model_present(settings.ollama_model):
                readiness.status = "ready"
                readiness.ollama_reachable = True
                readiness.model_present = True
                readiness.pull_progress_percent = None
                await asyncio.sleep(settings.readiness_recheck_seconds)
                continue

            readiness.status = "pulling"
            readiness.ollama_reachable = True
            readiness.model_present = False
            async for event in client.pull_model(
                settings.ollama_model, timeout=settings.ollama_pull_timeout_seconds
            ):
                readiness.pull_progress_percent = _progress_percent(event)

            readiness.status = "ready"
            readiness.model_present = True
            readiness.pull_progress_percent = None
        except (OllamaUnavailableError, OllamaTimeoutError):
            readiness.status = "degraded"
            readiness.ollama_reachable = False
            await asyncio.sleep(settings.pull_retry_backoff_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            readiness.status = "error"
            logger.exception("model bootstrap failed, retrying")
            await asyncio.sleep(settings.pull_retry_backoff_seconds)
