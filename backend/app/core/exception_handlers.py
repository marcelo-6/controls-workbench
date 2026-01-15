"""
Global exception handling for the FastAPI application.

This module centralizes translation of internal exceptions into the standard
API response envelope (`APIResponse`). It ensures:

- A uniform error contract for the frontend.
- JSON-safe response content (no raw datetime objects).
- Stable error codes for programmatic handling.
- High-quality server logs for unexpected failures.

Usage:
    Call `register_exception_handlers(app)` during app creation.

Design notes:
- Domain/service code should raise `AppError` subclasses from `app.core.errors`.
- Request validation errors are converted to a `validation_error` response.
- Unexpected exceptions are converted to `internal_error` and logged with stack trace.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    AuthError,
    BadRequestError,
    DBError,
    NotFoundError,
    StorageError,
)
from app.core.responses import fail

logger = logging.getLogger(__name__)


def _http_status_for_app_error(exc: AppError) -> int:
    """
    Map domain-level errors to HTTP status codes.

    Args:
        exc: An `AppError` raised by domain/services/infra.

    Returns:
        int: Appropriate HTTP status code for the exception type.
    """
    if isinstance(exc, AuthError):
        return 401
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, BadRequestError):
        return 400
    if isinstance(exc, (StorageError, DBError)):
        return 500
    # Default for unknown AppError subclasses.
    return 500


def _format_validation_fields(exc: RequestValidationError) -> dict[str, Any]:
    """
    Convert FastAPI/Pydantic validation errors into a frontend-friendly mapping.

    Formatting rules:
    - Drop the leading "body" segment for body payload errors.
    - Preserve "query", "path", "header" prefixes.
    - Use dotted paths for nested fields.

    Args:
        exc: The RequestValidationError instance.

    Returns:
        dict[str, Any]: Field path -> message mapping.
    """
    out: dict[str, Any] = {}
    for err in exc.errors():
        loc = list(err.get("loc", ()))

        # Drop "body" prefix for body errors: ("body","a","b") -> ("a","b")
        if loc and loc[0] == "body":
            loc = loc[1:] or ["body"]

        key = ".".join(str(x) for x in loc) if loc else "request"
        msg = str(err.get("msg", "Invalid value"))
        out[key] = msg

    return out


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers on the given FastAPI application.

    After registration, the application will:
    - Convert `AppError` exceptions into a standardized API error envelope.
    - Convert FastAPI validation errors into a standardized API error envelope.
    - Convert unexpected exceptions into `internal_error`, logging full details.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """
        Handle domain/service errors (HTTP-independent).

        Args:
            _request: FastAPI request (unused; request_id is injected via middleware).
            exc: The raised AppError.

        Returns:
            JSONResponse: Standard API error envelope with mapped HTTP status.
        """
        status_code = _http_status_for_app_error(exc)
        payload = fail(code=exc.code, detail=exc.detail, fields=exc.fields)
        return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle request parsing/validation errors from FastAPI/Pydantic.

        Args:
            _request: FastAPI request (unused; request_id is injected via middleware).
            exc: Validation error produced by FastAPI/Pydantic.

        Returns:
            JSONResponse: Standard API error envelope with HTTP 422 status.
        """
        payload = fail(
            code="validation_error",
            detail="Request validation failed",
            fields=_format_validation_fields(exc) or None,
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        """
        Handle FastAPI/Starlette HTTPException instances.

        This ensures framework-level errors (e.g., explicit `raise HTTPException(...)`)
        are returned using the same `APIResponse` envelope as domain/service errors.

        Notes:
            - Uses `exc.status_code` as the HTTP status.
            - Uses a stable `http_error` code for the frontend.
            - `exc.detail` can be a string or structured object; we stringify for safety.

        Args:
            _request: FastAPI request (unused; request_id is injected via middleware).
            exc: The HTTPException instance.

        Returns:
            JSONResponse: Standard API error envelope with the exception status code.
        """
        payload = fail(code="http_error", detail=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_request: Request, exc: Exception) -> JSONResponse:
        """
        Handle unexpected exceptions (last-resort).

        Returns a generic error message to avoid leaking internals, while logging the
        full stack trace for debugging.

        Args:
            _request: FastAPI request (unused; request_id is injected via middleware).
            exc: The unexpected exception.

        Returns:
            JSONResponse: Standard API error envelope with HTTP 500 status.
        """
        logger.exception("Unhandled exception: %s", exc)
        payload = fail(code="internal_error", detail="An unexpected error occurred")
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
