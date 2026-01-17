# backend/app/api/routes/logs.py
"""
Server logs routes.

This is optional and intended for local debugging. It should not expose
sensitive information in production deployments.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_auth
from app.core.responses import APIResponse, ok
from app.core.settings import Settings, get_settings
from app.infra.storage.paths import logs_root

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/tail", response_model=APIResponse[dict], dependencies=[Depends(require_auth)])
def tail_api_log(
    lines: int = Query(default=200, ge=1, le=5000),
    settings: Settings = Depends(get_settings),
) -> APIResponse[dict]:
    """
    Tail the API log file.

    Args:
        lines: Number of lines to return from the end of the log.
        settings: App settings.

    Returns:
        APIResponse[dict]: `{ "lines": [..] }`
    """
    log_path = logs_root / "api.log"
    if not log_path.exists():
        return ok({"lines": []})

    text = log_path.read_text(encoding="utf-8", errors="replace")
    tail = text.splitlines()[-lines:]
    return ok({"lines": tail})
