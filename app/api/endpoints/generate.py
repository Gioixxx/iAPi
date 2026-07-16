from fastapi import APIRouter, Depends

from app.ai.services.generate_service import GenerateService
from app.api.deps import get_generate_service, get_optional_api_key
from app.schemas.generate import GenerateRequest, GenerateResponse

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    service: GenerateService = Depends(get_generate_service),
    _api_key: None = Depends(get_optional_api_key),
) -> GenerateResponse:
    return await service.generate(body)
