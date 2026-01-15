# backend/app/core/request_id.py
"""
Request correlation utilities.

This module stores the current request ID in a context variable so it can be
retrieved from anywhere in the call stack (routes, services, repos) without
explicitly threading the FastAPI/Starlette Request object everywhere.

Primary use cases:
- Correlating backend logs with client-visible errors and API responses.
- Attaching `request_id` to the standard API response `meta` section.
- Supporting async execution safely without global state.

Notes:
- Uses `contextvars`, which is safe for async code and isolates values per task.
- The middleware is responsible for setting and clearing the request_id for
  each request lifecycle.
"""

from __future__ import annotations

import contextvars

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def set_request_id(value: str | None) -> None:
    """
    Set the request ID for the current execution context.

    This is typically called by request middleware at the beginning of a request,
    and cleared when the request finishes to prevent leakage across tasks.

    Args:
        value: The request ID value to associate with the current context,
               or None to clear it.
    """
    _request_id.set(value)


def get_request_id() -> str | None:
    """
    Get the request ID for the current execution context.

    Returns:
        str | None: The request ID if one has been assigned, otherwise None.
    """
    return _request_id.get()
