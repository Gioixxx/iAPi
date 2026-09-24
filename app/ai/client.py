from app.ai.base import LLMClient
from app.ai.lmstudio_client import LMStudioClient
from app.ai.ollama_client import OllamaClient
from app.core.config import Settings


def create_llm_client(settings: Settings) -> LLMClient:
    """Picks the backend from LLM_PROVIDER. Explicit on purpose, never auto-detected: with
    both servers up, which model answered must not depend on which one replied first."""
    if settings.llm_provider == "lmstudio":
        return LMStudioClient(
            base_url=settings.lmstudio_base_url,
            connect_timeout=settings.ollama_connect_timeout_seconds,
            request_timeout=settings.ollama_request_timeout_seconds,
            api_token=settings.lmstudio_api_token,
            reasoning_effort=settings.lmstudio_reasoning_effort or None,
        )
    return OllamaClient(
        base_url=settings.ollama_base_url,
        connect_timeout=settings.ollama_connect_timeout_seconds,
        request_timeout=settings.ollama_request_timeout_seconds,
    )
