from pydantic import BaseModel

from app.core.readiness import ReadinessStatus


class HealthResponse(BaseModel):
    status: ReadinessStatus
    ollama_reachable: bool
    model: str
    model_present: bool
    pull_progress_percent: int | None = None
