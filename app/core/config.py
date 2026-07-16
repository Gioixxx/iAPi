from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_request_timeout_seconds: float = 120.0
    ollama_pull_timeout_seconds: float = 1800.0
    ollama_connect_timeout_seconds: float = 5.0
    pull_retry_backoff_seconds: float = 30.0
    readiness_recheck_seconds: float = 60.0
    max_prompt_chars: int = 8000
    log_level: str = "INFO"


settings = Settings()
