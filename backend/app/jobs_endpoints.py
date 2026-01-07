from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .api_models import (
    APIResponse,
    ArtifactsList,
    ArtifactInfo,
    CreateJobRequest,
    JobCreated,
    JobState,
    JobStatus,
    LinesPayload,
    RecentRuns,
    RunSummary,
)
from .api_response import ok
from .auth import require_auth
from .run_models import RunMeta, RunState, utcnow
from .run_storage import (
    append_event,
    events_path,
    meta_path,
    read_meta,
    read_state,
    run_dir,
    state_path,
    tail_lines,
    touch_meta_access,
    write_meta,
    write_state,
)
from .tasks import run_tool_job
from .tools_registry import TOOLS
from .uploads_storage import upload_dir

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _artifacts_ready(job_id: str) -> bool:
    rd = run_dir(job_id)
    return (rd / "graph" / "graph.json").exists() and (rd / "report" / "report.json").exists() and (rd / "report" / "summary.md").exists()


@router.post("", response_model=APIResponse[JobCreated])
def create_job(request: Request, body: CreateJobRequest, user: str = Depends(require_auth)):
    if body.tool_id not in TOOLS:
        raise HTTPException(status_code=400, detail="Unknown tool_id")
    if not upload_dir(body.upload_id).exists():
        raise HTTPException(status_code=404, detail="Upload not found")

    job_id = str(uuid.uuid4())

    # Initialize run files
    meta = RunMeta(job_id=job_id, tool_id=body.tool_id, created_at=utcnow(), last_accessed_at=utcnow())
    write_meta(meta)

    state = RunState(job_id=job_id, tool_id=body.tool_id, status=JobStatus.queued, created_at=utcnow())
    write_state(state)

    append_event(job_id, "Job queued")

    # Enqueue
    run_tool_job(job_id, body.tool_id, body.upload_id, body.params)

    return ok(JobCreated(job_id=job_id), message="Job created", request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}", response_model=APIResponse[JobState])
def get_job(request: Request, job_id: str, user: str = Depends(require_auth)):
    st = read_state(job_id)
    meta = read_meta(job_id)
    if not st or not meta:
        raise HTTPException(status_code=404, detail="Job not found")

    touch_meta_access(job_id)

    payload = JobState(
        job_id=job_id,
        tool_id=st.tool_id,
        status=st.status,
        created_at=st.created_at,
        started_at=st.started_at,
        finished_at=st.finished_at,
        progress_hint=st.progress_hint,
        artifacts_ready=_artifacts_ready(job_id),
    )
    return ok(payload, request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}/events", response_model=APIResponse[LinesPayload])
def get_events(request: Request, job_id: str, tail: int = Query(default=2000, ge=1, le=20000), user: str = Depends(require_auth)):
    p = events_path(job_id)
    lines = tail_lines(p, tail)
    return ok(LinesPayload(lines=lines), request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}/artifacts", response_model=APIResponse[ArtifactsList])
def list_artifacts(request: Request, job_id: str, user: str = Depends(require_auth)):
    rd = run_dir(job_id)
    if not rd.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts = []
    for rel in ["graph/graph.json", "report/report.json", "report/summary.md"]:
        fp = rd / rel
        if fp.exists() and fp.is_file():
            artifacts.append(
                ArtifactInfo(
                    path=rel,
                    size_bytes=fp.stat().st_size,
                    url=f"/api/jobs/{job_id}/artifact?path={rel}",
                )
            )
    return ok(ArtifactsList(artifacts=artifacts), request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}/artifact")
def get_artifact(job_id: str, path: str, user: str = Depends(require_auth)):
    rd = run_dir(job_id)
    fp = (rd / path).resolve()
    if not str(fp).startswith(str(rd.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not fp.exists() or not fp.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(fp)


# Run history (for UI)
runs_router = APIRouter(prefix="/api/runs", tags=["runs"])


@runs_router.get("/recent", response_model=APIResponse[RecentRuns])
def recent_runs(request: Request, limit: int = Query(default=20, ge=1, le=200), user: str = Depends(require_auth)):
    runs_root = run_dir("").parent
    items = []
    if runs_root.exists():
        for d in runs_root.iterdir():
            if not d.is_dir():
                continue
            job_id = d.name
            meta = read_meta(job_id)
            st = read_state(job_id)
            if meta and st:
                items.append(
                    RunSummary(
                        job_id=job_id,
                        tool_id=meta.tool_id,
                        status=st.status,
                        created_at=meta.created_at,
                        last_accessed_at=meta.last_accessed_at,
                    )
                )
    items.sort(key=lambda x: x.created_at, reverse=True)
    return ok(RecentRuns(runs=items[:limit]), request_id=getattr(request.state, "request_id", None))
