from pydantic import BaseModel

from app.core.config import LLMProvider
from app.core.readiness import ReadinessStatus


class HealthResponse(BaseModel):
    status: ReadinessStatus
    provider: LLMProvider
    llm_reachable: bool
    # Deprecated alias of llm_reachable, from before LM Studio support: kept so 0.1.x
    # callers that read it keep working. Always equal to llm_reachable.
    ollama_reachable: bool
    model: str
    model_present: bool
    pull_progress_percent: int | None = None
