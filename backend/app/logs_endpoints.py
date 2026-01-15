from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .api_models import APIResponse, LinesPayload
from .api_response import ok
from .auth import require_auth
from .core.settings import settings
from .run_storage import tail_lines

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _log_path(name: str) -> Path:
    if name not in {"api", "worker"}:
        raise HTTPException(status_code=400, detail="Invalid log name")
    return Path(settings.data_dir) / "logs" / f"{name}.log"


@router.get("/latest", response_model=APIResponse[LinesPayload])
def latest(
    request: Request,
    name: str = Query(default="api"),
    user: str = Depends(require_auth),
):
    p = _log_path(name)
    lines = tail_lines(p, 1)
    return ok(LinesPayload(lines=lines), request_id=getattr(request.state, "request_id", None))


@router.get("/tail", response_model=APIResponse[LinesPayload])
def tail(
    request: Request,
    n: int = Query(default=2000, ge=1, le=20000),
    name: str = Query(default="api"),
    user: str = Depends(require_auth),
):
    p = _log_path(name)
    lines = tail_lines(p, n)
    return ok(LinesPayload(lines=lines), request_id=getattr(request.state, "request_id", None))


@router.get("/download")
def download(user: str = Depends(require_auth)):
    logs_dir = Path(settings.data_dir) / "logs"
    if not logs_dir.exists():
        raise HTTPException(status_code=404, detail="No logs directory")

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fp in logs_dir.glob("*"):
            if fp.is_file():
                z.write(fp, arcname=fp.name)
    mem.seek(0)
    return StreamingResponse(
        mem,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=logs.zip"},
    )
