# backend/tests/unit/infra/storage/test_artifacts_fs.py
"""
Unit tests for `app.infra.storage.artifacts_fs`.

These tests ensure:
- Artifacts are written and read correctly under a job directory.
- Parent directories are created as needed.
- Path traversal attempts are blocked (delegated to `artifact_path`).
- Job directory cleanup removes all artifacts.

Artifacts are blobs: bytes on disk, metadata in SQLite (handled elsewhere).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infra.storage.artifacts_fs import (
    delete_job_dir,
    read_artifact_bytes,
    write_artifact_bytes,
)
from app.infra.storage.paths import job_dir


def test_write_and_read_artifact_round_trip(isolated_data_dir: Path) -> None:
    """
    Writing an artifact should create parent directories and allow a clean read back.
    """
    job_id = "job-1"
    rel = "artifacts/graph.json"
    content = b'{"nodes": [], "edges": []}'

    p = write_artifact_bytes(job_id, rel, content)
    assert p.exists()
    assert p.read_bytes() == content

    loaded = read_artifact_bytes(job_id, rel)
    assert loaded == content

    # Ensure the artifact lives under the expected job directory.
    assert p.is_relative_to(job_dir(job_id).resolve())


def test_write_artifact_blocks_path_traversal(isolated_data_dir: Path) -> None:
    """
    Writing must reject artifact paths that attempt to escape the job directory.
    """
    job_id = "job-2"
    with pytest.raises(ValueError):
        write_artifact_bytes(job_id, "../evil.txt", b"x")

    with pytest.raises(ValueError):
        write_artifact_bytes(job_id, "../../evil.txt", b"x")


def test_delete_job_dir_removes_job_files(isolated_data_dir: Path) -> None:
    """
    Job directory cleanup should remove all artifacts for the given job_id.
    """
    job_id = "job-3"
    write_artifact_bytes(job_id, "artifacts/a.bin", b"a")
    write_artifact_bytes(job_id, "reports/b.txt", b"b")

    d = job_dir(job_id)
    assert d.exists()

    delete_job_dir(job_id)
    assert not d.exists()
