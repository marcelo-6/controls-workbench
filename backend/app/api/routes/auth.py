# backend/app/api/routes/auth.py
"""
Authentication routes.

This backend uses a simple session-based authentication model intended for a
single-user local workflow (no multi-user management).

Endpoints:
- POST /api/auth/login
- POST /api/auth/logout
- GET  /api/auth/me
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas.auth import AuthState, LoginRequest
from app.core.errors import AuthError
from app.core.responses import APIResponse, ok
from app.core.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse[AuthState])
def login(
    request: Request, body: LoginRequest, settings: Settings = Depends(get_settings)
) -> APIResponse[AuthState]:
    """
    Authenticate the current session.

    Args:
        request: FastAPI request (session is attached by SessionMiddleware).
        body: Login payload containing password.
        settings: Application settings.

    Returns:
        APIResponse[AuthState]: Auth state for the current session.

    Raises:
        AuthError: If the password is incorrect.
    """
    if body.password != settings.app_password:
        raise AuthError(detail="Invalid password")

    request.session["authed"] = True
    return ok(AuthState(authed=True))


@router.post("/logout", response_model=APIResponse[AuthState])
def logout(request: Request) -> APIResponse[AuthState]:
    """
    Clear authentication for the current session.

    Args:
        request: FastAPI request.

    Returns:
        APIResponse[AuthState]: Updated auth state (false).
    """
    request.session.clear()
    return ok(AuthState(authed=False))


@router.get("/me", response_model=APIResponse[AuthState])
def me(request: Request) -> APIResponse[AuthState]:
    """
    Return whether the current session is authenticated.

    Args:
        request: FastAPI request.

    Returns:
        APIResponse[AuthState]: Current auth state.
    """
    return ok(AuthState(authed=bool(request.session.get("authed"))))
