# backend/app/domain/jobs/service.py
"""
Jobs domain service.

This module implements the application-level workflow for job lifecycle operations.
A "job" represents a tool execution request tied to an existing upload.

Design goals:
- HTTP-independent (no FastAPI imports).
- Repository-driven state (SQLite is source of truth for job status/events/artifact index).
- Deterministic orchestration (enqueue is injected so unit tests can run synchronously).
- String timestamps (ISO UTC) to align with repository schema and JSON safety.

Key responsibilities:
- create job rows and enqueue execution
- read/touch jobs and list recent jobs
- delete jobs (DB rows + best-effort filesystem cleanup)
- read events and artifact index rows (artifact bytes read via infra storage)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.errors import BadRequestError, NotFoundError
from app.core.time import utcnow_iso
from app.infra.db.repos.artifacts import ArtifactsRepo
from app.infra.db.repos.events import EventsRepo
from app.infra.db.repos.jobs import JobsRepo
from app.infra.db.repos.uploads import UploadsRepo
from app.infra.storage.artifacts_fs import delete_job_dir, read_artifact_bytes

EnqueueFn = Callable[[str], None]


@dataclass(frozen=True)
class JobCreated:
    """
    Domain result returned after creating a job.

    Attributes:
        job_id: Stable identifier for the created job.
        tool_id: Tool identifier requested for execution.
        upload_id: Upload identifier containing the job inputs.
        status: Initial job status (typically 'queued').
        created_at: Creation timestamp (UTC ISO string).
    """

    job_id: str
    tool_id: str
    upload_id: str
    status: str
    created_at: str


class JobsService:
    """
    Orchestrates job lifecycle operations.

    This class deliberately keeps logic thin and testable by delegating persistence to:
    - JobsRepo, EventsRepo, ArtifactsRepo (SQLite)
    - artifacts_fs for filesystem operations
    """

    def __init__(
        self,
        *,
        uploads_repo: UploadsRepo,
        jobs_repo: JobsRepo,
        events_repo: EventsRepo,
        artifacts_repo: ArtifactsRepo,
        enqueue: EnqueueFn,
    ) -> None:
        """
        Initialize the jobs service.

        Args:
            uploads_repo: Repository used to validate upload existence.
            jobs_repo: Repository used to create/read/update/delete job state.
            events_repo: Repository used to append and read job events.
            artifacts_repo: Repository used to list and locate job artifacts.
            enqueue: Callable used to enqueue job execution (Huey in prod, sync in tests).
        """
        self._uploads = uploads_repo
        self._jobs = jobs_repo
        self._events = events_repo
        self._artifacts = artifacts_repo
        self._enqueue = enqueue

    def create_job(
        self, *, tool_id: str, upload_id: str, params: dict[str, Any] | None = None
    ) -> JobCreated:
        """
        Create a new job row and enqueue execution.

        Args:
            tool_id: Tool identifier (e.g., 'ignition.project.explorer').
            upload_id: Existing upload identifier.
            params: Optional JSON-serializable tool parameters.

        Returns:
            JobCreated: Domain result describing the newly created job.

        Raises:
            BadRequestError: If the referenced upload does not exist.
        """
        if self._uploads.get(upload_id) is None:
            raise BadRequestError(code="upload_not_found", detail=f"Upload not found: {upload_id}")

        now = utcnow_iso()
        job_id = self._jobs_id()
        params_json = json.dumps(params or {}, separators=(",", ":"), sort_keys=True)

        self._jobs.create(
            job_id=job_id,
            tool_id=tool_id,
            upload_id=upload_id,
            created_at=now,
            last_accessed_at=now,
            status="queued",
            params_json=params_json,
        )

        self._events.append(
            job_id=job_id, ts=now, level="info", message="Job created", kind="lifecycle"
        )

        self._enqueue(job_id)
        return JobCreated(
            job_id=job_id,
            tool_id=tool_id,
            upload_id=upload_id,
            status="queued",
            created_at=now,
        )

    def get_job(self, *, job_id: str) -> dict[str, Any]:
        """
        Fetch a job row by id and update last_accessed_at.

        Args:
            job_id: Job identifier.

        Returns:
            dict[str, Any]: Job row.

        Raises:
            NotFoundError: If job does not exist.
        """
        row = self._jobs.get(job_id)
        if row is None:
            raise NotFoundError(code="job_not_found", detail=f"Job not found: {job_id}")

        self._jobs.touch(job_id, last_accessed_at=utcnow_iso())
        return row

    def recent_jobs(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """
        Return most recent jobs for UI lists.

        Args:
            limit: Max jobs to return.

        Returns:
            list[dict[str, Any]]: Recent jobs (created_at DESC).
        """
        return self._jobs.recent(limit=limit)

    def delete_job(self, *, job_id: str) -> None:
        """
        Hard-delete a job row and remove its job directory.

        Deletion order:
        1) Best-effort delete filesystem job directory.
        2) Delete job row from DB (cascades events/artifacts via FKs).

        Args:
            job_id: Job identifier.

        Raises:
            NotFoundError: If job does not exist.
        """
        if self._jobs.get(job_id) is None:
            raise NotFoundError(code="job_not_found", detail=f"Job not found: {job_id}")

        delete_job_dir(job_id)
        self._jobs.delete(job_id)

    def tail_events(self, *, job_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        """
        Tail the job event log.

        Args:
            job_id: Job identifier.
            limit: Max events to return.

        Returns:
            list[dict[str, Any]]: Events for display (chronological).
        """
        return self._events.tail(job_id=job_id, limit=limit)

    def list_artifacts(self, *, job_id: str) -> list[dict[str, Any]]:
        """
        List indexed artifacts for a job.

        Args:
            job_id: Job identifier.

        Returns:
            list[dict[str, Any]]: Artifact rows from DB.
        """
        return self._artifacts.list(job_id=job_id)

    def read_artifact(self, *, job_id: str, kind: str) -> tuple[bytes, str]:
        """
        Read an artifact payload by kind.

        Args:
            job_id: Job identifier.
            kind: Artifact kind key (e.g., 'graph', 'tree', 'report').

        Returns:
            tuple[bytes, str]: (artifact bytes, content_type)

        Raises:
            NotFoundError: If artifact row not found.
        """
        row = self._artifacts.get(job_id=job_id, kind=kind)
        if row is None:
            raise NotFoundError(
                code="artifact_not_found",
                detail=f"Artifact not found for job={job_id} kind={kind}",
            )
        payload = read_artifact_bytes(job_id, row["rel_path"])
        return payload, (row.get("content_type") or "application/octet-stream")

    @staticmethod
    def _jobs_id() -> str:
        """
        Generate a new job id.

        Returns:
            str: Unique job id.
        """
        # keep it simple; switch to UUID if you prefer
        import uuid

        return str(uuid.uuid4())
