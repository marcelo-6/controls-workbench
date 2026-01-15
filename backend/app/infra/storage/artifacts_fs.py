# backend/app/infra/storage/artifacts_fs.py
"""
Filesystem-backed storage for job artifacts.

Artifacts are blobs produced by tools (e.g., graph JSON, tree index, reports).
This module provides safe read/write primitives that operate strictly under
a job directory and prevent path traversal.

Queryable metadata about artifacts (kind, content type, size) lives in SQLite
and is managed by `infra/db/repos/artifacts_repo.py`.
"""

from __future__ import annotations

from pathlib import Path

from app.infra.storage.paths import artifact_path, job_dir


def write_artifact_bytes(job_id: str, rel_path: str, data: bytes) -> Path:
    """
    Write artifact bytes to the job directory, creating parent directories as needed.

    Args:
        job_id: Job identifier.
        rel_path: Relative path under the job directory (e.g., "artifacts/graph.json").
        data: Artifact bytes to write.

    Returns:
        Path: Absolute path to the written artifact file.

    Raises:
        ValueError: If `rel_path` attempts traversal outside the job directory.
        OSError: If filesystem operations fail.
    """
    p = artifact_path(job_id, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def read_artifact_bytes(job_id: str, rel_path: str) -> bytes:
    """
    Read artifact bytes from the job directory.

    Args:
        job_id: Job identifier.
        rel_path: Relative artifact path.

    Returns:
        bytes: Artifact content.

    Raises:
        FileNotFoundError: If the artifact does not exist.
        ValueError: If `rel_path` attempts traversal outside the job directory.
        OSError: If the read fails.
    """
    p = artifact_path(job_id, rel_path)
    return p.read_bytes()


def delete_job_dir(job_id: str) -> None:
    """
    Delete the entire job directory and all contained artifacts.

    This is blob cleanup; callers should coordinate with the DB to remove job rows
    (and cascaded events/artifacts) separately.

    Args:
        job_id: Job identifier.
    """
    d = job_dir(job_id)
    if not d.exists():
        return

    import shutil

    shutil.rmtree(d, ignore_errors=True)
