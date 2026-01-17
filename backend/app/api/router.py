# backend/app/api/router.py
"""
Top-level API router composition.

This module defines the HTTP routing surface for the backend and is the single
place where individual route modules are included.

Design goals:
- Keep routing concerns centralized and discoverable.
- Keep per-feature routes isolated in `app.api.routes.*`.
- Provide a stable `/api` prefix for all endpoints consumed by the UI.

Notes:
- Business logic must live in domain services; routes only validate inputs,
  call services, and return standardized `APIResponse` envelopes.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import artifacts, auth, events, info, logs, runs, tools, uploads


def build_api_router() -> APIRouter:
    """
    Construct and return the API router mounted under `/api`.

    Returns:
        APIRouter: Router containing all application endpoints.
    """
    router = APIRouter(prefix="/api")

    router.include_router(info.router)
    router.include_router(auth.router)
    router.include_router(uploads.router)
    router.include_router(runs.router)
    router.include_router(events.router)
    router.include_router(artifacts.router)
    router.include_router(tools.router)
    router.include_router(logs.router)

    return router
