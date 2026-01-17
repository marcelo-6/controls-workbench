# backend/app/api/routes/events.py
"""
Events routes.

Events are the tail-able output stream for a run, stored in the DB for fast
polling and retention without scanning files.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_jobs_service, require_auth
from app.api.schemas.events import EventLine, EventsPayload
from app.core.responses import APIResponse, ok
from app.domain.jobs.service import JobsService

router = APIRouter(prefix="/runs", tags=["events"])


@router.get(
    "/{job_id}/events",
    response_model=APIResponse[EventsPayload],
    dependencies=[Depends(require_auth)],
)
def tail_events(
    job_id: str,
    limit: int = Query(default=2000, ge=1, le=10000),
    svc: JobsService = Depends(get_jobs_service),
) -> APIResponse[EventsPayload]:
    """
    Return the most recent events for a run.

    Args:
        job_id: Run identifier.
        limit: Max number of lines.
        svc: Jobs service.

    Returns:
        APIResponse[EventsPayload]: Event lines.
    """
    rows = svc.tail_events(job_id=job_id, limit=limit)
    lines = [
        EventLine(
            ts=r.get("ts") or r.get("created_at") or "",
            level=r.get("level") or "info",
            message=r.get("message") or "",
            kind=r.get("kind"),
            payload=r.get("payload"),
        )
        for r in rows
    ]
    return ok(EventsPayload(lines=lines))
