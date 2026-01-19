# backend/app/api/deps.py
"""
Dependency providers for the FastAPI API layer.

This module centralizes construction of request-scoped dependencies:
- Settings
- SQLite connections (via `db_session`)
- Repository instances
- Service instances
- Auth guards

Keeping these here ensures routes remain thin and consistent, while also
making it straightforward to override dependencies in tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from app.core.errors import AuthError
from app.core.settings import Settings, get_settings
from app.domain.jobs.service import JobsService
from app.domain.tools.registry import ToolsRegistry, build_tools_registry
from app.domain.tools.service import ToolsService
from app.domain.uploads.service import UploadsService
from app.infra.db.db import db_session
from app.infra.db.repos.artifacts import ArtifactsRepo
from app.infra.db.repos.events import EventsRepo
from app.infra.db.repos.jobs import JobsRepo
from app.infra.db.repos.uploads import UploadsRepo
from app.infra.queue.runner import build_queue_runner


@dataclass(frozen=True)
class Repos:
    """Container for all repository instances created per DB session."""

    uploads: UploadsRepo
    jobs: JobsRepo
    events: EventsRepo
    artifacts: ArtifactsRepo


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[object]:
    """
    Provide a request-scoped SQLite connection.

    Args:
        settings: Application settings (dependency injected).

    Yields:
        sqlite3.Connection: Open connection with proper row_factory configured.
    """
    with db_session(settings.index_db) as conn:
        yield conn


def get_repos(conn=Depends(get_db)) -> Repos:
    """
    Create repositories bound to the current request DB connection.

    Args:
        conn: SQLite connection (dependency injected).

    Returns:
        Repos: Repository bundle.
    """
    return Repos(
        uploads=UploadsRepo(conn),
        jobs=JobsRepo(conn),
        events=EventsRepo(conn),
        artifacts=ArtifactsRepo(conn),
    )


@lru_cache
def get_tools_registry() -> ToolsRegistry:
    """
    Build and cache the tools registry.

    Returns:
        ToolsRegistry: Registry mapping tool IDs to runnable definitions.
    """
    return build_tools_registry()


def require_auth(request: Request) -> None:
    """
    Enforce session-based authentication.

    This guard is intended to be used as a FastAPI dependency:
        Depends(require_auth)

    Args:
        request: Incoming request.

    Raises:
        AuthError: If the session is not authenticated.
    """
    if not bool(request.session.get("authed")):
        raise AuthError(detail="Authentication required")


def get_paths(settings: Annotated[Settings, Depends(get_settings)]) -> Path:
    """
    Construct the filesystem path helper (pure `pathlib.Path` API).

    Args:
        settings: Application settings.

    Returns:
        Paths: Path helper rooted under settings.data_dir.
    """
    return settings.data_dir


def get_queue_runner(settings: Annotated[Settings, Depends(get_settings)]):
    """
    Construct the queue runner.

    In production this typically enqueues Huey tasks; in tests this can be a
    synchronous runner that calls task implementations locally.

    Args:
        settings: Application settings.

    Returns:
        Queue runner instance compatible with `enqueue_job(job_id)`.
    """
    return build_queue_runner(settings)


def get_uploads_service(
    repos: Annotated[Repos, Depends(get_repos)],
) -> UploadsService:
    """
    Construct the uploads domain service.

    Returns:
        UploadsService: Service instance.
    """
    return UploadsService(
        uploads_repo=repos.uploads,
    )


def get_jobs_service(
    repos: Annotated[Repos, Depends(get_repos)],
    enqueue=Depends(get_queue_runner),
) -> JobsService:
    """
    Construct the jobs/runs domain service.

    Returns:
        JobsService: Service instance.
    """
    return JobsService(
        uploads_repo=repos.uploads,
        jobs_repo=repos.jobs,
        events_repo=repos.events,
        artifacts_repo=repos.artifacts,
        enqueue=enqueue.enqueue_job,
    )


def get_tools_service(
    repos: Annotated[Repos, Depends(get_repos)],
    registry: Annotated[ToolsRegistry, Depends(get_tools_registry)],
) -> ToolsService:
    """
    Construct the tools execution service.

    Returns:
        ToolsService: Service instance.
    """
    return ToolsService(
        registry=registry,
        jobs_repo=repos.jobs,
        uploads_repo=repos.uploads,
        events_repo=repos.events,
        artifacts_repo=repos.artifacts,
    )
