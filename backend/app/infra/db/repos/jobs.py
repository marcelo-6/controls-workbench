# backend/app/infra/db/repos/jobs.py
"""
Jobs repository.

This repository provides SQL-only access to the `jobs` table and core queries used
by the UI (recent jobs, job status).

Notes:
- Soft delete is supported via `deleted_at` (optional). Repos expose it, but
  policy lives in the retention service.
- `artifacts_ready` and `total_artifacts_bytes` exist specifically to avoid
  filesystem scanning during polling and retention.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.errors import DBError


class JobsRepo:
    """SQL access layer for the `jobs` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        job_id: str,
        tool_id: str,
        upload_id: str,
        created_at: str,
        last_accessed_at: str,
        status: str = "queued",
        params_json: str | None = None,
    ) -> None:
        """Insert a new job row."""
        try:
            self._conn.execute(
                """
                INSERT INTO jobs (
                  job_id, tool_id, upload_id, status,
                  created_at, last_accessed_at, params_json,
                  artifacts_ready, total_artifacts_bytes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    job_id,
                    tool_id,
                    upload_id,
                    status,
                    created_at,
                    last_accessed_at,
                    params_json,
                ),
            )
        except Exception as e:
            raise DBError(detail=f"Failed to create job {job_id}: {e}") from e

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Fetch a job row by id."""
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None

    def touch(self, job_id: str, *, last_accessed_at: str) -> None:
        """Update last_accessed_at for retention bookkeeping."""
        try:
            self._conn.execute(
                "UPDATE jobs SET last_accessed_at = ? WHERE job_id = ?",
                (last_accessed_at, job_id),
            )
        except Exception as e:
            raise DBError(detail=f"Failed to touch job {job_id}: {e}") from e

    def set_status(
        self,
        job_id: str,
        *,
        status: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        progress: int | None = None,
        progress_hint: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        error_detail_path: str | None = None,
        artifacts_ready: int | None = None,
        total_artifacts_bytes: int | None = None,
    ) -> None:
        """
        Update job status and related fields.

        Only non-None fields are updated to avoid clobbering existing state.
        """
        fields: list[str] = ["status = ?"]
        params: list[Any] = [status]

        def _add(name: str, value: Any) -> None:
            if value is not None:
                fields.append(f"{name} = ?")
                params.append(value)

        _add("started_at", started_at)
        _add("finished_at", finished_at)
        _add("progress", progress)
        _add("progress_hint", progress_hint)
        _add("error_code", error_code)
        _add("error_message", error_message)
        _add("error_detail_path", error_detail_path)
        _add("artifacts_ready", artifacts_ready)
        _add("total_artifacts_bytes", total_artifacts_bytes)

        params.append(job_id)

        try:
            self._conn.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?",
                tuple(params),
            )
        except Exception as e:
            raise DBError(detail=f"Failed to update job {job_id}: {e}") from e

    def recent(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Return the most recent non-deleted jobs (created_at DESC)."""
        rows = self._conn.execute(
            """
            SELECT * FROM jobs
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, job_id: str) -> None:
        """Hard delete a job row; cascades events/artifacts by FK."""
        try:
            self._conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        except Exception as e:
            raise DBError(detail=f"Failed to delete job {job_id}: {e}") from e
