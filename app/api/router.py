from fastapi import APIRouter

from app.api.endpoints import generate, health, ui

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(generate.router)
api_router.include_router(ui.router)
