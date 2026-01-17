from __future__ import annotations

import asyncio

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import build_api_router

# Routers (still old for now - Step 6 will move them)
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware
from app.core.responses import ok
from app.core.settings import settings
from app.infra.db.db import init_db


def create_app() -> FastAPI:
    """
    FastAPI application factory.

    Responsibilities (by design):
    - Construct the FastAPI app with project metadata from settings.
    - Register global middleware (request_id, sessions).
    - Register global exception handlers (uniform APIResponse envelope).
    - Mount routers (legacy routers for now; will be migrated in Step 6).
    - Register startup lifecycle hooks.

    Business logic must not live here; it belongs in domain services.
    """
    configure_logging()
    api_logger = get_logger("api", str(settings.logs_dir / "api.log"))

    app = FastAPI(
        title=settings.project_name,
        description=settings.project_description,
        version=settings.backend_version,
    )

    # Middleware
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=False,
    )

    # Exception handlers (uniform API response contract)
    register_exception_handlers(app)

    app.include_router(build_api_router())

    # Simple health endpoint (kept stable for docker/ops checks)
    @app.get("/api/health")
    async def health():
        """
        Lightweight liveness endpoint.

        Returns:
            APIResponse[dict]: Always returns success with a small payload.
        """
        return ok({"status": "ok"})

    async def _retention_loop() -> None:
        """
        Periodic retention maintenance.

        Note:
            This is intentionally conservative and can be replaced later with:
            - event-driven cleanup (e.g., after upload/job completion)
            - a scheduled task via Huey
            - or a dedicated maintenance service
        """
        while False:  # TODO: enable later (or run on-demand)
            try:
                # del_uploads = cleanup_uploads()
                # run_stats = cleanup_runs()
                pass
                # api_logger.info("retention: deleted_uploads=%s stats=%s", del_uploads, run_stats)
            except Exception:
                pass
                # api_logger.exception("retention loop error: %s", e)
            await asyncio.sleep(60 * 60)

    @app.on_event("startup")
    async def _startup() -> None:
        """
        Startup hook for lightweight initialization.

        Responsibilities:
        - Initialize required local storage/database structures.
        - Start background maintenance tasks (optional).

        Heavy work belongs in worker processes, not the API process.
        """
        api_logger.info("API startup")
        try:
            init_db(settings.db_path)
        except Exception as e:
            api_logger.exception("DB init failed: %s", e)

        asyncio.create_task(_retention_loop())

    return app


# Uvicorn entrypoint expects `app` at module scope
app = create_app()
