from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

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


@router.post(
    "/generate/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "NDJSON, one event per line: any number of "
                '{"type": "delta", "text"}, then one {"type": "done", ...GenerateResponse} '
                'or one {"type": "error", "status", "detail"}.'
            ),
            "content": {"application/x-ndjson": {}},
        }
    },
)
async def generate_stream(
    body: GenerateRequest,
    service: GenerateService = Depends(get_generate_service),
    _api_key: None = Depends(get_optional_api_key),
) -> StreamingResponse:
    lines = await service.open_stream(body)
    return StreamingResponse(
        lines,
        media_type="application/x-ndjson",
        # X-Accel-Buffering: a reverse proxy in front must not hold the chunks back.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
