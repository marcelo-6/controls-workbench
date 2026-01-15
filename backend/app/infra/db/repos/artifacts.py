# backend/app/infra/db/repos/artifacts.py
"""
Job artifacts repository.

Artifacts are payloads stored on disk (graph/tree/report/summary/etc). The DB stores
only an index of what exists and lightweight metadata needed by the UI:
- kind
- rel_path
- content_type
- size_bytes
- created_at
- meta_json (optional)

Unique constraint: one artifact of a given kind per job (UNIQUE(job_id, kind)).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.errors import DBError


class ArtifactsRepo:
    """SQL access layer for the `job_artifacts` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(
        self,
        *,
        job_id: str,
        kind: str,
        rel_path: str,
        content_type: str,
        size_bytes: int,
        created_at: str,
        meta_json: str | None = None,
    ) -> None:
        """Insert or update a job artifact row by (job_id, kind)."""
        try:
            self._conn.execute(
                """
                INSERT INTO job_artifacts (
                  job_id, kind, rel_path, content_type, size_bytes, created_at, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, kind) DO UPDATE SET
                  rel_path=excluded.rel_path,
                  content_type=excluded.content_type,
                  size_bytes=excluded.size_bytes,
                  created_at=excluded.created_at,
                  meta_json=excluded.meta_json
                """,
                (
                    job_id,
                    kind,
                    rel_path,
                    content_type,
                    size_bytes,
                    created_at,
                    meta_json,
                ),
            )
        except Exception as e:
            raise DBError(
                code="DB_INSERT_ARTIFACT_FAILED",
                detail=f"Failed to upsert artifact {kind} for job {job_id}: {e}",
            ) from e

    def list(self, job_id: str) -> list[dict[str, Any]]:
        """List all artifacts for a job."""
        rows = self._conn.execute(
            """
            SELECT id, job_id, kind, rel_path, content_type, size_bytes, created_at, meta_json
            FROM job_artifacts
            WHERE job_id = ?
            ORDER BY kind ASC
            """,
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, *, job_id: str, kind: str) -> dict[str, Any] | None:
        """Fetch a single artifact row by (job_id, kind)."""
        row = self._conn.execute(
            """
            SELECT id, job_id, kind, rel_path, content_type, size_bytes, created_at, meta_json
            FROM job_artifacts
            WHERE job_id = ? AND kind = ?
            """,
            (job_id, kind),
        ).fetchone()
        return dict(row) if row else None
