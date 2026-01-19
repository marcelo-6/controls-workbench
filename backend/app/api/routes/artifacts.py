# backend/app/api/routes/artifacts.py
"""
Artifacts routes.

Artifacts are run outputs. Metadata is returned via `APIResponse`, but binary
downloads return a `FileResponse` (not wrapped) to preserve content-type and
streaming semantics.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse

from app.api.deps import get_jobs_service, require_auth
from app.api.schemas.artifacts import ArtifactInfo, ArtifactsList
from app.core.responses import APIResponse, ok
from app.domain.jobs.service import JobsService

router = APIRouter(prefix="/runs", tags=["artifacts"])


@router.get(
    "/{job_id}/artifacts",
    response_model=APIResponse[ArtifactsList],
    dependencies=[Depends(require_auth)],
)
def list_artifacts(
    job_id: str, svc: JobsService = Depends(get_jobs_service)
) -> APIResponse[ArtifactsList]:
    """
    List artifacts available for a run.

    Args:
        job_id: Run identifier.
        svc: Jobs service.

    Returns:
        APIResponse[ArtifactsList]: Artifact metadata list.
    """
    rows = svc.list_artifacts(job_id=job_id)
    artifacts = [
        ArtifactInfo(
            kind=r["kind"],
            relPath=r["rel_path"],
            contentType=r.get("content_type") or "application/octet-stream",
            sizeBytes=int(r.get("size_bytes") or 0),
            meta=r.get("meta") if isinstance(r.get("meta"), dict) else None,
        )
        for r in rows
    ]
    return ok(ArtifactsList(artifacts=artifacts))


@router.get("/{job_id}/artifacts/{kind}", dependencies=[Depends(require_auth)])
def download_artifact(
    job_id: str, kind: str, svc: JobsService = Depends(get_jobs_service)
) -> FileResponse:
    """
    Download a specific artifact by kind.

    Args:
        job_id: Run identifier.
        kind: Artifact kind key (e.g., "graph", "report", "summary").
        svc: Jobs service.

    Returns:
        FileResponse: Streaming file response.
    """
    payload, content_type = svc.read_artifact(job_id=job_id, kind=kind)
    # If the artifact is JSON, wrap it in APIResponse
    if content_type == "application/json":
        return ok(json.loads(payload))

    # Otherwise return raw bytes
    return Response(content=payload, media_type=content_type)
