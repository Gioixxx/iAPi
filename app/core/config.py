from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["ollama", "lmstudio"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: LLMProvider = "ollama"

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"

    lmstudio_base_url: str = "http://host.docker.internal:1234"
    lmstudio_model: str = "google/gemma-4-e2b"
    lmstudio_api_token: str | None = None
    # "none" switches thinking off on reasoning models (gemma-4, qwen3 think by default):
    # measured 3.6x faster on qwen3-0.6b for an email-length reply. Empty string = not sent.
    lmstudio_reasoning_effort: str = "none"

    # Historical OLLAMA_ names, kept for existing deployments: they apply to both providers.
    ollama_request_timeout_seconds: float = 120.0
    ollama_pull_timeout_seconds: float = 1800.0
    ollama_connect_timeout_seconds: float = 5.0

    pull_retry_backoff_seconds: float = 30.0
    readiness_recheck_seconds: float = 60.0
    max_prompt_chars: int = 8000
    log_level: str = "INFO"

    @property
    def llm_model(self) -> str:
        return self.lmstudio_model if self.llm_provider == "lmstudio" else self.ollama_model


settings = Settings()
