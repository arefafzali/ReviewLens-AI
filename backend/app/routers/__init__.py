"""API router registration."""

from fastapi import APIRouter

from .chat import router as chat_router
from .context import router as context_router
from .health import router as health_router
from .ingestion import router as ingestion_router
from .products import router as products_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(context_router, tags=["context"])
api_router.include_router(ingestion_router, tags=["ingestion"])
api_router.include_router(products_router, tags=["products"])
api_router.include_router(chat_router, tags=["chat"])
