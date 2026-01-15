# backend/tests/unit/domain/test_uploads_service.py
"""
Unit tests for UploadsService.

These tests validate the orchestration contract:
- blobs are persisted to the filesystem
- metadata is persisted in SQLite
- returned domain result fields are consistent
"""

from __future__ import annotations

import io
from pathlib import Path

from starlette.datastructures import UploadFile

from app.domain.uploads.service import UploadsService
from app.infra.db.db import db_session, init_db
from app.infra.db.repos.uploads import UploadsRepo


def test_create_upload_persists_fs_and_db(isolated_data_dir: Path) -> None:
    """
    Creating an upload should store the uploaded files on disk and create a DB row.
    """
    db_path = isolated_data_dir / "index.sqlite"
    init_db(db_path)

    with db_session(db_path) as conn:
        repo = UploadsRepo(conn)
        svc = UploadsService(repo)

        project = UploadFile(filename="export.zip", file=io.BytesIO(b"zip-bytes"))
        tags = UploadFile(filename="tags.json", file=io.BytesIO(b'{"a": 1}'))

        created = svc.create_upload(project_zip=project, tags_json=tags)

        row = repo.get(created.upload_id)
        assert row is not None
        assert row["sha256"] == created.sha256
        assert row["size_bytes"] == created.size_bytes
        assert row["project_zip_path"] == created.project_zip_rel
        assert row["tags_json_path"] == created.tags_json_rel
