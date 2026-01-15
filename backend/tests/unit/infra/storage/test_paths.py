# backend/tests/unit/infra/storage/test_paths.py
"""
Unit tests for `app.infra.storage.paths`.

These tests validate:
- The application computes its filesystem layout using `pathlib.Path`.
- Artifact path construction defends against path traversal attacks.

All tests use an isolated DATA_DIR to ensure no real filesystem state is used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infra.storage.paths import artifact_path, data_root, job_dir


def test_data_root_uses_configured_data_dir(isolated_data_dir: Path) -> None:
    """
    Verify that `data_root()` reflects the configured `DATA_DIR`.

    This confirms settings integration and provides confidence that all derived
    storage roots (uploads/jobs/logs) stay under the expected base directory.
    """
    assert data_root() == isolated_data_dir


def test_artifact_path_allows_normal_relative_paths(isolated_data_dir: Path) -> None:
    """
    Verify that a normal relative artifact path resolves under the job directory.

    This is the expected happy-path for writing artifacts like:
    - artifacts/graph.json
    - artifacts/tree.json
    - reports/summary.md
    """
    jid = "job-123"
    rel = "artifacts/graph.json"

    p = artifact_path(jid, rel)
    base = job_dir(jid).resolve()

    assert p.is_relative_to(base)
    assert p.name == "graph.json"


def test_artifact_path_blocks_path_traversal(isolated_data_dir: Path) -> None:
    """
    Verify that path traversal attempts are rejected.

    A malicious or buggy caller must not be able to escape the job directory by
    providing paths such as '../../etc/passwd' or absolute paths.
    """
    jid = "job-123"
    with pytest.raises(ValueError):
        artifact_path(jid, "../../etc/passwd")

    with pytest.raises(ValueError):
        artifact_path(jid, "../outside.txt")

    # Absolute paths must also be rejected because they escape the job directory.
    # (On Windows in the future, this guards against `C:\\...` as well.)
    with pytest.raises(ValueError):
        artifact_path(jid, str(Path("/tmp/evil.txt")))
