from fastapi import Depends, Header, Request

from app.ai.base import LLMClient
from app.ai.services.generate_service import GenerateService
from app.core.config import Settings, settings
from app.core.readiness import ModelReadiness


def get_settings() -> Settings:
    return settings


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


def get_readiness(request: Request) -> ModelReadiness:
    return request.app.state.readiness


def get_generate_service(
    client: LLMClient = Depends(get_llm_client),
    readiness: ModelReadiness = Depends(get_readiness),
    app_settings: Settings = Depends(get_settings),
) -> GenerateService:
    return GenerateService(client, app_settings, readiness)


async def get_optional_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """No-op today (v1 has no auth, per decision). Kept as a real dependency already
    wired into /generate's signature so adding a real API-key check later is a one-line
    change to this function's body, not a route signature change."""
    return None
