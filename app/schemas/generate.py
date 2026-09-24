from pydantic import BaseModel, Field

from app.core.config import settings


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=settings.max_prompt_chars)
    system: str | None = Field(default=None, min_length=1, max_length=settings.max_prompt_chars)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)


class GenerateResponse(BaseModel):
    response: str
    model: str
    eval_count: int | None = None
    total_duration_ms: int | None = None
