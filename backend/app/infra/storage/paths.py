# backend/app/infra/storage/paths.py
"""
Filesystem path utilities for blob storage.

This module is the single source of truth for all filesystem layout decisions.
It provides small, deterministic helpers that return `pathlib.Path` objects only.

Design rules
------------
- No string paths are returned from this module. Callers may convert to `str`
  only at the boundary to third-party APIs that require strings.
- Paths are derived from `Settings.data_dir`, allowing clean test overrides.
- This module does *not* perform I/O. It only *computes* paths.
- All artifact path construction must defend against path traversal attempts.

Blob storage responsibilities
-----------------------------
The filesystem stores "blobs" (uploaded files and generated artifacts).
Queryable metadata and indexes live in SQLite (see `infra/db/*`).
"""

from __future__ import annotations

from pathlib import Path

from app.core.settings import get_settings


def data_root() -> Path:
    """
    Return the filesystem root directory for all persisted application data.

    This is the directory under which uploads, job artifacts, logs, and any other
    filesystem-backed blobs are stored.

    Returns:
        Path: Root data directory (always absolute).
    """
    settings = get_settings()
    return Path(settings.data_dir).resolve()


def uploads_root() -> Path:
    """
    Return the directory that contains all uploaded blobs.

    Returns:
        Path: `<data_root>/uploads`
    """
    return data_root() / "uploads"


def jobs_root() -> Path:
    """
    Return the directory that contains all job working directories and artifacts.

    Returns:
        Path: `<data_root>/jobs`
    """
    return data_root() / "jobs"


def logs_root() -> Path:
    """
    Return the directory where backend log files are stored.

    Returns:
        Path: `<data_root>/logs`
    """
    return data_root() / "logs"


def upload_dir(upload_id: str) -> Path:
    """
    Compute the directory for a specific upload.

    Args:
        upload_id: Stable upload identifier.

    Returns:
        Path: `<uploads_root>/<upload_id>`
    """
    return uploads_root() / upload_id


def job_dir(job_id: str) -> Path:
    """
    Compute the directory for a specific job.

    Args:
        job_id: Stable job identifier.

    Returns:
        Path: `<jobs_root>/<job_id>`
    """
    return jobs_root() / job_id


def artifact_path(job_id: str, rel_path: str) -> Path:
    """
    Safely compute an artifact path within a job directory.

    This function prevents path traversal attempts (e.g., `../../etc/passwd`) by
    resolving the final path and ensuring it remains within the job directory.

    Args:
        job_id: Job identifier.
        rel_path: Artifact path relative to the job directory (POSIX-style or native).

    Returns:
        Path: Absolute path to the artifact under `<jobs_root>/<job_id>/...`.

    Raises:
        ValueError: If `rel_path` escapes the job directory.
    """
    base = job_dir(job_id).resolve()
    candidate = (base / rel_path).resolve()

    # `Path.is_relative_to` is available in Python 3.9+.
    if not candidate.is_relative_to(base):
        raise ValueError("Artifact path traversal attempt blocked")

    return candidate
