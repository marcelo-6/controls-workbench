# backend/app/infra/queue/tasks.py
"""
Queue task definitions.

This module defines Huey tasks that act as thin adapters between the queue and
domain services.

Rules:
- Task functions should contain minimal logic.
- All business behavior lives in domain services (e.g. ToolsService).
- Exceptions should bubble so the job runner can mark failure (ToolsService does that).

In production, these tasks are executed by the Huey consumer process.
"""

from __future__ import annotations

from app.infra.queue.huey_app import get_huey

huey = get_huey()


@huey.task()
def run_job(job_id: str) -> None:
    """
    Execute a single job by id.

    This task is intentionally thin: it resolves a service graph and delegates
    to `ToolsService.run_job`.

    Args:
        job_id: Job identifier to execute.
    """
    # Local import prevents heavyweight imports at module import time and
    # avoids circular dependencies.
    from app.core.settings import get_settings
    from app.domain.tools.registry import build_tools_registry
    from app.domain.tools.service import ToolsService
    from app.infra.db.db import db_session
    from app.infra.db.repos.artifacts import ArtifactsRepo
    from app.infra.db.repos.events import EventsRepo
    from app.infra.db.repos.jobs import JobsRepo
    from app.infra.db.repos.uploads import UploadsRepo

    s = get_settings()
    with db_session(s.index_db) as conn:
        svc = ToolsService(
            registry=build_tools_registry(),
            jobs_repo=JobsRepo(conn),
            uploads_repo=UploadsRepo(conn),
            events_repo=EventsRepo(conn),
            artifacts_repo=ArtifactsRepo(conn),
        )
        svc.run_job(job_id=job_id)
