from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .api_models import LoginRequest, LoginResponse, MeResponse
from .core.responses import APIResponse, ok
from .core.settings import settings


def require_auth(request: Request) -> str:
    if not request.session.get("authed"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return request.session.get("username", "user")


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse[LoginResponse])
def login(request: Request, body: LoginRequest):
    if body.password != settings.app_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    request.session["authed"] = True
    request.session["username"] = "user"
    return ok(
        LoginResponse(ok=True),
        message="Logged in",
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/me", response_model=APIResponse[MeResponse])
def me(request: Request):
    authed = bool(request.session.get("authed"))
    if not authed:
        return ok(
            MeResponse(ok=False, username=""),
            message="Not logged in",
            request_id=getattr(request.state, "request_id", None),
        )
    return ok(
        MeResponse(ok=True, username=request.session.get("username", "user")),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/logout", response_model=APIResponse[LoginResponse])
def logout(request: Request, user: str = Depends(require_auth)):
    request.session.clear()
    return ok(
        LoginResponse(ok=True),
        message="Logged out",
        request_id=getattr(request.state, "request_id", None),
    )
