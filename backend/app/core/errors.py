# backend/app/core/errors.py
"""
Domain-level exception types.

This module defines HTTP-independent error classes used throughout services and
infrastructure. The API layer is responsible for converting these exceptions
into HTTP responses using the standard API response contract.

Why this exists:
- Keeps business logic decoupled from FastAPI/Starlette concerns.
- Produces consistent, structured error codes for the frontend.
- Improves testability: services raise domain errors, tests assert error codes.

Conventions:
- Every error has a stable `code` suitable for frontend branching.
- `detail` is human-readable and safe to display to operators.
- `fields` optionally includes structured context (validation, missing keys, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AppError(Exception):
    """
    Base class for application errors raised by domain/services/infra code.

    Attributes:
        code: Stable machine-readable error identifier.
        detail: Human-readable explanation.
        fields: Optional structured context (e.g., per-field validation errors).
    """

    code: str
    detail: str
    fields: dict[str, Any] | None = None


class AuthError(AppError):
    """Raised when authentication or authorization fails."""

    pass


class NotFoundError(AppError):
    """Raised when a required resource (job, upload, artifact) does not exist."""

    pass


class BadRequestError(AppError):
    """Raised for invalid input data or unsupported operations."""

    pass


class StorageError(AppError):
    """Raised when filesystem operations fail (read/write/permissions/corruption)."""

    pass


class DBError(AppError):
    """Raised when database operations fail or invariants are violated."""

    pass
