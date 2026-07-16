import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.ai.client import OllamaClient
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.readiness import ModelReadiness, bootstrap_model

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = OllamaClient(
        base_url=settings.ollama_base_url,
        connect_timeout=settings.ollama_connect_timeout_seconds,
        request_timeout=settings.ollama_request_timeout_seconds,
    )
    readiness = ModelReadiness()
    app.state.ollama_client = client
    app.state.readiness = readiness

    bootstrap_task = asyncio.create_task(bootstrap_model(client, settings, readiness))
    try:
        yield
    finally:
        bootstrap_task.cancel()
        try:
            await bootstrap_task
        except asyncio.CancelledError:
            pass
        await client.aclose()


app = FastAPI(title="iAPi", lifespan=lifespan)
app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
