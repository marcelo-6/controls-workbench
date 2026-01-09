from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .api_models import ErrorField
from .api_response import fail

# Routers
from .auth import router as auth_router
from .config import settings
from .index_db import get_index_db
from .jobs_endpoints import router as jobs_router
from .jobs_endpoints import runs_router
from .logging_conf import setup_logger
from .logs_endpoints import router as logs_router
from .middleware import RequestIdMiddleware
from .retention import cleanup_runs, cleanup_uploads
from .storage import ensure_dirs
from .tools_endpoints import ign as ignition_router
from .tools_endpoints import router as tools_router
from .uploads_endpoints import router as uploads_router

ensure_dirs()
api_logger = setup_logger("api", str(Path(settings.data_dir) / "logs" / "api.log"))

app = FastAPI(title="Controls Workbench API", version="0.1.0")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(code="HTTP_ERROR", detail=str(exc.detail), request_id=rid).model_dump(
            mode="json", by_alias=True
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None)
    fields = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        fields.append(ErrorField(field=loc or "body", message=err.get("msg", "Invalid value")))
    resp = fail(
        code="VALIDATION_ERROR",
        detail="Request validation failed",
        request_id=rid,
        fields=fields,
    )
    return JSONResponse(status_code=422, content=resp.model_dump(mode="json", by_alias=True))


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    api_logger.exception("Unhandled error request_id=%s: %s", rid, exc)
    resp = fail(code="INTERNAL_ERROR", detail="Internal server error", request_id=rid)
    return JSONResponse(status_code=500, content=resp.model_dump(mode="json", by_alias=True))


# Include routers
app.include_router(auth_router)
app.include_router(uploads_router)
app.include_router(jobs_router)
app.include_router(runs_router)
app.include_router(tools_router)
app.include_router(ignition_router)
app.include_router(logs_router)


async def _retention_loop():
    # small, safe loop; deletes old uploads and trims runs
    while False:  # TODO this should be run once when the user uploads something
        try:
            del_uploads = cleanup_uploads()
            run_stats = cleanup_runs()
            api_logger.info("retention: deleted_uploads=%s stats=%s", del_uploads, run_stats)
        except Exception as e:
            api_logger.exception("retention loop error: %s", e)
        await asyncio.sleep(60 * 60)  # hourly


@app.on_event("startup")
async def _startup():
    api_logger.info("API startup")
    # Initialize the SQLite catalog early (creates schema if missing).
    try:
        get_index_db()
    except Exception as e:
        api_logger.exception("Index DB init failed: %s", e)
    asyncio.create_task(_retention_loop())
