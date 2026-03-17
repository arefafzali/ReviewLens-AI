"""FastAPI application entrypoint."""

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api_metadata import APP_DESCRIPTION, APP_TITLE, APP_VERSION, OPENAPI_TAGS
from app.config import get_settings
from app.models.api_error import APIErrorResponse, ErrorDetail
from app.routers import api_router


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
) -> JSONResponse:
    payload = APIErrorResponse(
        error=ErrorDetail(code=code, message=message, details=dict(details) if details else None)
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
    )

    app.state.settings = settings
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": exc.errors(), "path": str(request.url.path)},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail) if exc.detail else "Request failed."
        return _error_response(
            status_code=exc.status_code,
            code=f"HTTP_{exc.status_code}",
            message=message,
            details={"path": str(request.url.path)},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
            details={"path": str(request.url.path), "exception": exc.__class__.__name__},
        )

    return app


app = create_app()
