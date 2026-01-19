# backend/app/infra/db/repos/uploads.py
"""
Uploads repository.

This repository provides SQL-only CRUD access to the `uploads` table.

Responsibilities:
- Insert and fetch upload metadata (paths, sizes, hashes).
- Update `last_accessed_at` on reads/usage (retention support).
- Perform hard delete or soft delete (status='deleted') if desired.

Non-responsibilities:
- No filesystem I/O (handled by infra/storage).
- No business rules (handled by domain services).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.errors import DBError
from app.core.logging import get_logger
from app.core.settings import settings

LOG = get_logger("api", str(settings.logs_dir / "api.log"))


class UploadsRepo:
    """SQL access layer for the `uploads` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        upload_id: str,
        created_at: str,
        last_accessed_at: str,
        project_zip_path: str,
        tags_json_path: str | None,
        size_bytes: int,
        sha256: str | None = None,
        status: str = "ready",
        meta_json: str | None = None,
    ) -> None:
        """Insert a new upload row."""
        try:
            LOG.debug(f"[{self.__class__.__name__}] Inserting upload metadata (db)")
            self._conn.execute(
                """
                INSERT INTO uploads (
                  upload_id, created_at, last_accessed_at,
                  project_zip_path, tags_json_path,
                  size_bytes, sha256, status, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    created_at,
                    last_accessed_at,
                    project_zip_path,
                    tags_json_path,
                    size_bytes,
                    sha256,
                    status,
                    meta_json,
                ),
            )
            LOG.debug(f"[{self.__class__.__name__}] Inserted upload metadata (db)")
        except Exception as e:
            raise DBError(
                code="DB_INSERT_UPLOAD_FAILED",
                detail=f"Failed to create upload {upload_id}: {e}",
            ) from e

    def get(self, upload_id: str) -> dict[str, Any] | None:
        """Fetch an upload row by id."""
        row = self._conn.execute(
            "SELECT * FROM uploads WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()
        return dict(row) if row else None

    def touch(self, upload_id: str, *, last_accessed_at: str) -> None:
        """Update last_accessed_at for retention bookkeeping."""
        try:
            self._conn.execute(
                "UPDATE uploads SET last_accessed_at = ? WHERE upload_id = ?",
                (last_accessed_at, upload_id),
            )
        except Exception as e:
            raise DBError(
                code="DB_UPDATE_LAST_ACCESSED_UPLOAD_FAILED",
                detail=f"Failed to touch upload {upload_id}: {e}",
            ) from e

    def delete(self, upload_id: str) -> None:
        """Hard delete an upload row (use carefully; RESTRICT may block)."""
        try:
            self._conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
        except Exception as e:
            raise DBError(
                code="DB_DELETE_UPLOAD_FAILED",
                detail=f"Failed to delete upload {upload_id}: {e}",
            ) from e
