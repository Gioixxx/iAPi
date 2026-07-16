from fastapi import Depends, Header, Request

from app.ai.client import OllamaClient
from app.ai.services.generate_service import GenerateService
from app.core.config import settings
from app.core.readiness import ModelReadiness


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.ollama_client


def get_readiness(request: Request) -> ModelReadiness:
    return request.app.state.readiness


def get_generate_service(
    client: OllamaClient = Depends(get_ollama_client),
    readiness: ModelReadiness = Depends(get_readiness),
) -> GenerateService:
    return GenerateService(client, settings, readiness)


async def get_optional_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """No-op today (v1 has no auth, per decision). Kept as a real dependency already
    wired into /generate's signature so adding a real API-key check later is a one-line
    change to this function's body, not a route signature change."""
    return None
