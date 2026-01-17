# backend/app/api/routes/runs.py
"""
Run (job) routes.

This module provides the UI-facing "runs" API. Internally, the persistence layer
uses the term "job"; externally, the UI uses "run". The router keeps the URL
shape stable while delegating all behavior to the domain `JobsService`.

Design goals:
- Thin routing layer: no DB access and no filesystem access here.
- Standardized API envelopes (`APIResponse`) for JSON endpoints.
- Service interface is source of truth for workflow behavior.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_jobs_service, require_auth
from app.api.schemas.runs import (
    CreateRunRequest,
    RecentRuns,
    RunCreated,
    RunStatus,
    RunSummary,
)
from app.core.responses import APIResponse, ok
from app.domain.jobs.service import JobsService

router = APIRouter(prefix="/runs", tags=["runs"])


def _to_run_status(row: dict[str, Any]) -> RunStatus:
    """
    Convert a DB job row into the UI-facing RunStatus schema.

    Args:
        row: DB row (dict) from JobsRepo.

    Returns:
        RunStatus: Normalized polling payload.
    """
    return RunStatus(
        jobId=row["job_id"],
        toolId=row["tool_id"],
        status=row["status"],
        progress=row.get("progress"),
        progressHint=row.get("progress_hint"),
        artifactsReady=bool(row.get("artifacts_ready") or 0),
        createdAt=row["created_at"],
        startedAt=row.get("started_at"),
        finishedAt=row.get("finished_at"),
        errorCode=row.get("error_code"),
        errorMessage=row.get("error_message"),
    )


def _to_run_summary(row: dict[str, Any]) -> RunSummary:
    """
    Convert a DB job row into a condensed summary.

    Args:
        row: DB row (dict) from JobsRepo.

    Returns:
        RunSummary: Condensed representation for recent listing.
    """
    return RunSummary(
        jobId=row["job_id"],
        toolId=row["tool_id"],
        status=row["status"],
        createdAt=row["created_at"],
    )


@router.get(
    "/recent",
    response_model=APIResponse[RecentRuns],
    dependencies=[Depends(require_auth)],
)
def recent_runs(
    limit: int = Query(default=30, ge=1, le=200),
    svc: JobsService = Depends(get_jobs_service),
) -> APIResponse[RecentRuns]:
    """
    Return recent runs for the sidebar.

    Args:
        limit: Maximum number of runs to return.
        svc: Jobs service.

    Returns:
        APIResponse[RecentRuns]: Recent runs list.
    """
    rows = svc.recent_jobs(limit=limit)
    return ok(RecentRuns(runs=[_to_run_summary(r) for r in rows]))


@router.post("", response_model=APIResponse[RunCreated], dependencies=[Depends(require_auth)])
def create_run(
    body: CreateRunRequest,
    svc: JobsService = Depends(get_jobs_service),
) -> APIResponse[RunCreated]:
    """
    Create a new run and enqueue execution.

    Args:
        body: Run creation request.
        svc: Jobs service.

    Returns:
        APIResponse[RunCreated]: New run identifier.
    """
    created = svc.create_job(tool_id=body.tool_id, upload_id=body.upload_id, params=body.params)
    return ok(RunCreated(jobId=created.job_id))


@router.get(
    "/{job_id}",
    response_model=APIResponse[RunStatus],
    dependencies=[Depends(require_auth)],
)
def get_run(
    job_id: str,
    svc: JobsService = Depends(get_jobs_service),
) -> APIResponse[RunStatus]:
    """
    Retrieve run status (used for polling).

    Args:
        job_id: Run/job identifier.
        svc: Jobs service.

    Returns:
        APIResponse[RunStatus]: Current run state.
    """
    row = svc.get_job(job_id=job_id)
    return ok(_to_run_status(row))


@router.delete("/{job_id}", response_model=APIResponse[dict], dependencies=[Depends(require_auth)])
def delete_run(job_id: str, svc: JobsService = Depends(get_jobs_service)) -> APIResponse[dict]:
    """
    Delete a run and all associated state (events/artifacts) and blobs.

    Args:
        job_id: Run identifier.
        svc: Jobs service.

    Returns:
        APIResponse[dict]: Deletion acknowledgement.
    """
    svc.delete_job(job_id=job_id)
    return ok({"deleted": True, "jobId": job_id})
