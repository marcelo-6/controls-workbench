# backend/app/domain/tools/service.py
"""
Tools execution orchestration.

This service is the runtime boundary between:
- Tool execution logic (pure-ish runner callables)
- Persistent job state (SQLite)
- Artifact persistence (filesystem) and indexing (SQLite)
- Event logging (SQLite)

Responsibilities:
- Validate the job record and tool registration.
- Transition job state: queued → running → success/failed.
- Provide a ToolContext implementation for runners.
- Catch exceptions and translate them into stable job failure fields.

This is the replacement for older "tasks.py" job logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import BadRequestError, NotFoundError
from app.core.time import utcnow_iso
from app.domain.tools.registry import ToolContext, ToolsRegistry
from app.infra.db.repos.artifacts import ArtifactsRepo
from app.infra.db.repos.events import EventsRepo
from app.infra.db.repos.jobs import JobsRepo
from app.infra.db.repos.uploads import UploadsRepo
from app.infra.storage.artifacts_fs import write_artifact_bytes
from app.infra.storage.uploads_fs import get_tags_json_path, get_upload_zip_path


@dataclass
class _ToolContextImpl:
    """
    Default ToolContext implementation used by ToolsService.

    This context centralizes persistence patterns so tool runners remain focused
    on computing outputs rather than handling storage/indexing details.
    """

    job_id: str
    upload_id: str
    events: EventsRepo
    artifacts: ArtifactsRepo

    def emit_event(
        self,
        # *,
        level: str,
        message: str,
        kind: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Append a job event row."""
        self.events.append(
            job_id=self.job_id,
            level=level,
            ts=utcnow_iso(),
            message=message,
            kind=kind,
            payload_json=payload,
        )

    def get_project_zip_path(self) -> str:
        """Return absolute filesystem path to the saved project zip."""
        return str(get_upload_zip_path(self.upload_id))

    def get_tags_json_path(self) -> str | None:
        """Return absolute filesystem path to the optional tags json."""
        p = get_tags_json_path(self.upload_id)
        return str(p) if p else None

    def write_artifact(
        self,
        *,
        kind: str,
        rel_path: str,
        content_type: str,
        data: bytes,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Persist an artifact and index it.

        Args:
            kind: Stable artifact kind key (e.g., 'graph', 'tree', 'report').
            rel_path: Relative path within the job directory.
            content_type: MIME type for downloads.
            data: Bytes to write.
            meta: Optional JSON-serializable metadata.
        """
        p = write_artifact_bytes(self.job_id, rel_path, data)
        self.artifacts.upsert(
            job_id=self.job_id,
            kind=kind,
            rel_path=rel_path,
            content_type=content_type,
            size_bytes=p.stat().st_size,
            created_at=utcnow_iso(),
            meta_json=meta,
        )


class ToolsService:
    """
    Executes a job by resolving its tool runner and coordinating persistence.

    This is the main correctness boundary for:
    - job state transitions
    - event logging surfaced in the UI
    - artifact persistence/indexing
    """

    def __init__(
        self,
        *,
        registry: ToolsRegistry,
        jobs_repo: JobsRepo,
        uploads_repo: UploadsRepo,
        events_repo: EventsRepo,
        artifacts_repo: ArtifactsRepo,
    ) -> None:
        self._registry = registry
        self._jobs = jobs_repo
        self._uploads = uploads_repo
        self._events = events_repo
        self._artifacts = artifacts_repo

    def run_job(self, *, job_id: str) -> None:
        """
        Run a job end-to-end.

        Args:
            job_id: Job identifier.

        Raises:
            NotFoundError: If the job does not exist.
            BadRequestError: If tool_id is unknown or upload is missing.
            Exception: Re-raised tool exceptions after marking job failed.
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(code="job_not_found", detail=f"Job not found: {job_id}")

        tool_id = job["tool_id"]
        upload_id = job["upload_id"]

        spec = self._registry.get_spec(tool_id)
        runner = self._registry.get_runner(tool_id)
        if spec is None or runner is None:
            raise BadRequestError(code="unknown_tool", detail=f"Unknown tool_id: {tool_id}")

        if self._uploads.get(upload_id) is None:
            raise BadRequestError(code="upload_not_found", detail=f"Upload not found: {upload_id}")

        # Mark running
        self._jobs.set_status(
            job_id,
            status="running",
            started_at=utcnow_iso(),
            progress=0,
            progress_hint=f"Running {spec.name}",
        )
        self._events.append(
            job_id=job_id,
            ts=utcnow_iso(),
            level="info",
            message=f"Tool started: {tool_id}",
            kind="lifecycle",
        )

        ctx: ToolContext = _ToolContextImpl(
            job_id=job_id,
            upload_id=upload_id,
            events=self._events,
            artifacts=self._artifacts,
        )

        total_artifacts_bytes = 0

        try:
            runner(ctx)

            # Optional: compute bytes from DB artifact index instead of FS scan
            try:
                for a in self._artifacts.list(job_id=job_id):
                    total_artifacts_bytes += int(a.get("size_bytes") or 0)
            except Exception:
                total_artifacts_bytes = 0

            self._jobs.set_status(
                job_id,
                status="success",
                finished_at=utcnow_iso(),
                progress=100,
                progress_hint="Done",
                artifacts_ready=1,
                total_artifacts_bytes=total_artifacts_bytes or None,
            )
            self._events.append(
                job_id=job_id,
                level="info",
                ts=utcnow_iso(),
                message="Tool finished successfully",
                kind="lifecycle",
            )

        except Exception as exc:
            self._events.append(
                job_id=job_id,
                level="error",
                ts=utcnow_iso(),
                message=f"Tool failed: {exc}",
                kind="lifecycle",
            )
            self._jobs.set_status(
                job_id,
                status="failed",
                finished_at=utcnow_iso(),
                progress_hint="Failed",
                error_code="tool_failed",
                error_message=str(exc),
                artifacts_ready=1,  # job is terminal; UI can stop polling
                total_artifacts_bytes=total_artifacts_bytes or None,
            )
            raise
