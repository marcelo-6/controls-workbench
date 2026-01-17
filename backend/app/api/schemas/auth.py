# backend/app/api/schemas/auth.py
"""
Auth API schemas.

These models define the request/response shapes for session authentication.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request payload (password-only for local single-user workflows)."""

    password: str = Field(min_length=1)


class AuthState(BaseModel):
    """Represents whether the current session is authenticated."""

    authed: bool
