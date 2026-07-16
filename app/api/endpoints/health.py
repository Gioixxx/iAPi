from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_readiness
from app.core.config import settings
from app.core.readiness import ModelReadiness
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(readiness: ModelReadiness = Depends(get_readiness)) -> HealthResponse:
    body = HealthResponse(
        status=readiness.status,
        ollama_reachable=readiness.ollama_reachable,
        model=settings.ollama_model,
        model_present=readiness.model_present,
        pull_progress_percent=readiness.pull_progress_percent,
    )
    if not readiness.ollama_reachable:
        raise HTTPException(status_code=503, detail=body.model_dump())
    return body
