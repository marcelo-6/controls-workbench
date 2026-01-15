# backend/tests/unit/infra/storage/test_uploads_fs.py
"""
Unit tests for `app.infra.storage.uploads_fs`.

These tests validate that:
- Upload blobs are written to the correct filesystem location.
- Size accounting is correct.
- SHA-256 is computed deterministically across the saved content.
- Cleanup removes upload directories.

Uploads are treated as blobs: bytes on disk, metadata in SQLite (handled elsewhere).
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from starlette.datastructures import UploadFile

from app.infra.storage.paths import upload_dir
from app.infra.storage.uploads_fs import (
    DEFAULT_PROJECT_ZIP_NAME,
    DEFAULT_TAGS_JSON_NAME,
    delete_upload_files,
    get_tags_json_path,
    get_upload_zip_path,
    save_upload,
)


def test_save_upload_writes_project_zip_and_returns_metadata(
    isolated_data_dir: Path,
) -> None:
    """
    Saving an upload should:
    - Create the upload directory.
    - Persist the project zip under a stable name.
    - Return correct total size and sha256 of the written bytes.
    """
    upload_id = "upl-1"
    payload = b"zip-bytes-here"

    project = UploadFile(filename="export.zip", file=io.BytesIO(payload))
    saved = save_upload(upload_id, project, tags_json=None)

    assert saved.upload_id == upload_id
    assert saved.size_bytes == len(payload)
    assert saved.tags_json_rel is None

    expected_sha = hashlib.sha256(payload).hexdigest()
    assert saved.sha256 == expected_sha

    d = upload_dir(upload_id)
    assert d.exists() and d.is_dir()

    p = d / DEFAULT_PROJECT_ZIP_NAME
    assert p.exists()
    assert p.read_bytes() == payload

    assert get_upload_zip_path(upload_id) == p
    assert get_tags_json_path(upload_id) is None


def test_save_upload_writes_optional_tags_json_and_updates_sha(
    isolated_data_dir: Path,
) -> None:
    """
    When tags_json is provided, saving an upload should persist it and include it
    in size accounting and sha256 hashing (in a stable concatenation order).
    """
    upload_id = "upl-2"
    project_bytes = b"project-zip"
    tags_bytes = b'{"tags": ["a", "b"]}'

    project = UploadFile(filename="export.zip", file=io.BytesIO(project_bytes))
    tags = UploadFile(filename="tags.json", file=io.BytesIO(tags_bytes))

    saved = save_upload(upload_id, project, tags_json=tags)

    assert saved.size_bytes == len(project_bytes) + len(tags_bytes)
    assert saved.tags_json_rel == DEFAULT_TAGS_JSON_NAME

    expected_sha = hashlib.sha256(project_bytes + tags_bytes).hexdigest()
    assert saved.sha256 == expected_sha

    d = upload_dir(upload_id)
    assert (d / DEFAULT_PROJECT_ZIP_NAME).read_bytes() == project_bytes
    assert (d / DEFAULT_TAGS_JSON_NAME).read_bytes() == tags_bytes

    assert get_tags_json_path(upload_id) == (d / DEFAULT_TAGS_JSON_NAME)


def test_delete_upload_files_removes_upload_directory(isolated_data_dir: Path) -> None:
    """
    Upload cleanup should remove the upload directory and all stored blobs.
    """
    upload_id = "upl-3"
    project = UploadFile(filename="export.zip", file=io.BytesIO(b"abc"))
    save_upload(upload_id, project, tags_json=None)

    d = upload_dir(upload_id)
    assert d.exists()

    delete_upload_files(upload_id)
    assert not d.exists()
