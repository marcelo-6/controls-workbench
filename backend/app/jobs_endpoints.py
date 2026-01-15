from __future__ import annotations

import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .api_models import (
    ArtifactInfo,
    ArtifactsList,
    CreateJobRequest,
    DeleteRunsResult,
    JobCreated,
    JobState,
    JobStatus,
    LinesPayload,
    RecentRuns,
    RunSummary,
)
from .auth import require_auth
from .core.responses import APIResponse, ok
from .index_db import get_index_db
from .run_models import RunMeta, RunState, utcnow
from .run_storage import (
    append_event,
    events_path,
    read_meta,
    read_state,
    run_dir,
    tail_lines,
    touch_meta_access,
    write_meta,
    write_state,
)
from .storage import data_path
from .tasks import run_tool_job
from .tools_registry import TOOLS
from .uploads_storage import upload_dir

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _artifacts_ready(job_id: str) -> bool:
    rd = run_dir(job_id)
    return (
        (rd / "graph" / "graph.json").exists()
        and (rd / "report" / "report.json").exists()
        and (rd / "report" / "summary.md").exists()
    )


@router.post("", response_model=APIResponse[JobCreated])
def create_job(request: Request, body: CreateJobRequest, user: str = Depends(require_auth)):
    if body.tool_id not in TOOLS:
        raise HTTPException(status_code=400, detail="Unknown tool_id")
    if not upload_dir(body.upload_id).exists():
        raise HTTPException(status_code=404, detail="Upload not found")

    job_id = str(uuid.uuid4())

    # Initialize run files
    meta = RunMeta(
        job_id=job_id,
        tool_id=body.tool_id,
        created_at=utcnow(),
        last_accessed_at=utcnow(),
    )
    write_meta(meta)

    state = RunState(
        job_id=job_id,
        tool_id=body.tool_id,
        status=JobStatus.queued,
        created_at=utcnow(),
    )
    write_state(state)

    append_event(job_id, "Job queued")

    # Persist a run row so /api/runs/recent does not need to scan the filesystem.
    try:
        get_index_db().upsert_run(
            job_id=job_id,
            tool_id=body.tool_id,
            status=state.status.value,
            created_at=meta.created_at,
            last_accessed_at=meta.last_accessed_at,
            meta=meta.model_dump(mode="json", by_alias=True),
        )
    except Exception:
        pass

    # Enqueue
    run_tool_job(job_id, body.tool_id, body.upload_id, body.params)

    return ok(
        JobCreated(job_id=job_id),
        message="Job created",
        request_id=getattr(request.state, "request_id", None),
    )


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
def get_events(
    request: Request,
    job_id: str,
    tail: int = Query(default=2000, ge=1, le=20000),
    user: str = Depends(require_auth),
):
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
    return ok(
        ArtifactsList(artifacts=artifacts),
        request_id=getattr(request.state, "request_id", None),
    )


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
def recent_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    user: str = Depends(require_auth),
):
    # Preferred: SQLite index (fast, no disk walking)
    try:
        rows = get_index_db().list_recent_runs(limit)
        items = []
        for r in rows:
            if not r.created_at or not r.last_accessed_at:
                continue
            items.append(
                RunSummary(
                    job_id=r.job_id,
                    tool_id=r.tool_id,
                    status=JobStatus(r.status),
                    created_at=r.created_at,
                    last_accessed_at=r.last_accessed_at,
                )
            )
        return ok(
            RecentRuns(runs=items),
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception:
        # Fallback: filesystem scan (v0.1 behavior)
        runs_root = data_path("runs")
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
        return ok(
            RecentRuns(runs=items[:limit]),
            request_id=getattr(request.state, "request_id", None),
        )


@runs_router.delete("/{job_id}", response_model=APIResponse[DeleteRunsResult])
def delete_run(
    request: Request,
    job_id: str,
    force: bool = Query(default=False),
    user: str = Depends(require_auth),
):
    # Validate job_id (prevents weird path traversal too)
    try:
        uuid.UUID(job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid job_id (must be a UUID)") from exc

    st = read_state(job_id)
    if st and st.status in (JobStatus.queued, JobStatus.running) and not force:
        raise HTTPException(
            status_code=409,
            detail="Job is still running. Pass force=true to delete anyway.",
        )

    deleted_any = False
    errors: list[str] = []

    # 1) Delete filesystem run directory
    rd = run_dir(job_id)
    if rd.exists():
        try:
            shutil.rmtree(rd)
            deleted_any = True
        except Exception as e:
            errors.append(f"Failed to delete run directory: {e}")

    # 2) Delete from index DB (best effort)
    try:
        # If your get_index_db().delete_run returns affected rowcount, use it.
        affected = get_index_db().delete_run(job_id)
        if affected:
            deleted_any = True
    except Exception:
        # keep endpoint resilient if DB is down / not present
        pass

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    if not deleted_any:
        raise HTTPException(status_code=404, detail="Job not found")

    return ok(
        DeleteRunsResult(deleted=[job_id]),
        message="Run deleted",
        request_id=getattr(request.state, "request_id", None),
    )


@runs_router.delete("", response_model=APIResponse[DeleteRunsResult])
def clear_runs(
    request: Request,
    confirm: bool = Query(default=False),
    force: bool = Query(default=False),
    user: str = Depends(require_auth),
):
    """
    Deletes *all* runs from history:
      - deletes /data/runs/<job_id> directories
      - deletes rows from the index DB
    Safety:
      - requires confirm=true
      - will skip queued/running unless force=true
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Refusing to delete all runs without confirm=true",
        )

    runs_root = data_path("runs")
    deleted: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # Collect candidates from filesystem
    job_ids: list[str] = []
    if runs_root.exists():
        for d in runs_root.iterdir():
            if not d.is_dir():
                continue
            # only consider UUID-like dirs
            try:
                uuid.UUID(d.name)
            except Exception:
                continue
            job_ids.append(d.name)

    # Delete per-run so we can honor "skip running unless force"
    for job_id in job_ids:
        st = read_state(job_id)
        if st and st.status in (JobStatus.queued, JobStatus.running) and not force:
            skipped.append(job_id)
            continue

        rd = run_dir(job_id)
        if rd.exists():
            try:
                shutil.rmtree(rd)
                deleted.append(job_id)
            except Exception as e:
                errors.append(f"{job_id}: failed to delete run directory: {e}")
                continue
        else:
            # directory already gone; still try to delete DB row
            deleted.append(job_id)

        # Remove from index DB (best effort)
        try:
            get_index_db().delete_run(job_id)
        except Exception:
            pass

    # If we truly deleted everything and nothing was skipped, we can clear DB in one shot too.
    # (Optional optimization - safe even if table is already empty.)
    if force and not skipped:
        try:
            get_index_db().clear_runs()
        except Exception:
            pass

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return ok(
        DeleteRunsResult(deleted=deleted, skipped=skipped),
        message=f"Cleared runs (deleted={len(deleted)}, skipped={len(skipped)})",
        request_id=getattr(request.state, "request_id", None),
    )
