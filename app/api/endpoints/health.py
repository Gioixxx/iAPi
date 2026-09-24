from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_readiness, get_settings
from app.core.config import Settings
from app.core.readiness import ModelReadiness
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    readiness: ModelReadiness = Depends(get_readiness),
    app_settings: Settings = Depends(get_settings),
) -> HealthResponse:
    body = HealthResponse(
        status=readiness.status,
        provider=app_settings.llm_provider,
        llm_reachable=readiness.llm_reachable,
        ollama_reachable=readiness.llm_reachable,
        model=app_settings.llm_model,
        model_present=readiness.model_present,
        pull_progress_percent=readiness.pull_progress_percent,
    )
    if not readiness.llm_reachable:
        raise HTTPException(status_code=503, detail=body.model_dump())
    return body
