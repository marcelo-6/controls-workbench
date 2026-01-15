# backend/app/core/responses.py
"""
Standard API response contract.

This module defines a consistent, strongly typed response envelope used by all
HTTP endpoints. The goal is to keep frontend integration predictable and keep
error handling uniform.

Response envelope structure:
- `status`: high-level success/error
- `message`: optional human-friendly message
- `data`: typed payload (or None)
- `meta`: request correlation + timestamps
- `error`: structured error details on failures

Key design decisions:
- Uses Python 3.14 type parameters for `APIResponse[T]` to satisfy Ruff's
  modern generic rules and keep typing clean.
- Ensures JSON-safe output by keeping timestamps as ISO strings (not raw
  datetime objects).
- Automatically injects `request_id` into `meta` using the request-id context
  variable set by middleware.

Usage:
- Return `ok(payload)` from route handlers for successful responses.
- Raise domain exceptions (AppError subclasses) and let global handlers convert
  them to `fail(...)` responses, or call `fail(...)` directly for simple cases.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.request_id import get_request_id
from app.core.time import utcnow


class Status(StrEnum):
    """
    High-level status for API responses.

    Values:
        success: The request completed successfully.
        error: The request failed (see `error` field for details).
    """

    success = "success"
    error = "error"


class APIError(BaseModel):
    """
    Structured error payload included in API responses when `status="error"`.

    Attributes:
        code: Stable machine-readable error identifier. Suitable for frontend
              branching and localization.
        detail: Human-readable explanation of what went wrong.
        fields: Optional dictionary of field-specific error details (e.g.,
                validation failures, payload issues).
    """

    code: str
    detail: str
    fields: dict[str, Any] | None = None


class APIMeta(BaseModel):
    """
    Metadata attached to every API response.

    Attributes:
        request_id: A correlation ID for tracing a request end-to-end across
                    logs, client errors, and server responses.
        timestamp_utc: ISO-8601 timestamp (UTC) when the response was generated.
    """

    request_id: str | None = None
    timestamp_utc: str = Field(default_factory=lambda: utcnow().isoformat())


class APIResponse[T](BaseModel):
    """
    Standard API response envelope.

    Type parameter:
        T: The payload type stored in `data`.

    Attributes:
        status: Overall request status (`success` or `error`).
        message: Optional message intended for operators/users.
        data: Response payload. Present for successful responses.
        meta: Response metadata (request correlation + timestamp).
        error: Structured error information. Present for error responses.
    """

    status: Status
    message: str | None = None
    data: T | None = None
    meta: APIMeta = Field(default_factory=APIMeta)
    error: APIError | None = None


def ok[T](data: T, message: str | None = None) -> APIResponse[T]:
    """
    Build a successful APIResponse.

    Automatically populates:
    - `meta.request_id` from the request context (if available)
    - `meta.timestamp_utc` at response creation time

    Args:
        data: The typed response payload.
        message: Optional human-friendly message.

    Returns:
        APIResponse[T]: A response object with `status="success"`.
    """
    return APIResponse[T](
        status=Status.success,
        message=message,
        data=data,
        meta=APIMeta(request_id=get_request_id()),
        error=None,
    )


def fail(
    code: str,
    detail: str,
    *,
    message: str | None = None,
    fields: dict[str, Any] | None = None,
) -> APIResponse[None]:
    """
    Build a failure APIResponse.

    This function is most useful in:
    - global exception handlers that translate domain errors into HTTP responses
    - endpoints that deliberately return error envelopes without raising

    Args:
        code: Stable machine-readable error code.
        detail: Human-readable explanation of the error.
        message: Optional top-level message (often redundant with detail).
        fields: Optional dictionary for field-level details.

    Returns:
        APIResponse[None]: A response object with `status="error"` and no data.
    """
    return APIResponse[None](
        status=Status.error,
        message=message,
        data=None,
        meta=APIMeta(request_id=get_request_id()),
        error=APIError(code=code, detail=detail, fields=fields),
    )
