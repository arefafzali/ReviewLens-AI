"""API router registration."""

from fastapi import APIRouter

from .context import router as context_router
from .health import router as health_router
from .ingestion import router as ingestion_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(context_router, tags=["context"])
api_router.include_router(ingestion_router, tags=["ingestion"])
