# backend/app/core/middleware.py
"""
Request middleware.

This module contains middleware that applies cross-cutting concerns across all
requests. Middleware should remain small and focused, and must not contain
business logic.

Current responsibilities:
- Assign and propagate a request correlation ID (X-Request-ID).
- Store the request ID in a context variable so it can be included in API
  responses and logs without passing the Request object everywhere.

Why request IDs matter:
- Makes it easy to trace a user's action through logs, DB events, and errors.
- Enables support/debugging by sharing a single correlation value.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_id import set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures each request has a correlation ID.

    Behavior:
    - If the incoming request contains `X-Request-ID`, that value is used.
    - Otherwise, a new UUID4 string is generated.
    - The request ID is:
        - stored on `request.state.request_id`
        - stored in a context variable (for response helpers/logging)
        - returned to the client in the response header `X-Request-ID`

    Notes:
    - The context variable is cleared after request handling to prevent
      cross-request leakage in async environments.
    """

    header_name = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """
        Assign request ID, call downstream app, then attach response header.

        Args:
            request: Starlette request object.
            call_next: Next middleware/app in the chain.

        Returns:
            Response: The downstream response with X-Request-ID attached.
        """
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = rid
        set_request_id(rid)

        try:
            resp = await call_next(request)
        finally:
            # Ensure correlation does not leak into other async tasks/requests.
            set_request_id(None)

        resp.headers[self.header_name] = rid
        return resp
