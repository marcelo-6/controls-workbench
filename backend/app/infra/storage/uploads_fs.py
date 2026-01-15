# backend/app/infra/storage/uploads_fs.py
"""
Filesystem-backed storage for upload blobs.

This module is responsible for persisting user-provided upload files to disk and
returning deterministic metadata (size and sha256) for DB indexing.

Uploads are treated as blobs:
- The filesystem stores the bytes.
- SQLite stores metadata and references (paths, hashes, timestamps).

No SQLite access occurs here; callers (domain services) coordinate DB writes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.infra.storage.paths import upload_dir

DEFAULT_PROJECT_ZIP_NAME = "project.zip"
DEFAULT_TAGS_JSON_NAME = "tags.json"


@dataclass(frozen=True)
class SavedUpload:
    """
    Result of persisting an upload to disk.

    Attributes:
        upload_id: Identifier for the upload.
        upload_path: Directory where upload files were written.
        project_zip_rel: Relative filename for the saved project zip.
        tags_json_rel: Relative filename for the saved tags json (if any).
        size_bytes: Total bytes written across all saved files.
        sha256: SHA-256 hash computed across the concatenated bytes of saved files.
            (Stable for the exact saved content and order.)
    """

    upload_id: str
    upload_path: Path
    project_zip_rel: str
    tags_json_rel: str | None
    size_bytes: int
    sha256: str


def _copy_stream_and_hash(src: BinaryIO, dst: BinaryIO, hasher: hashlib._Hash) -> int:
    """
    Copy bytes from `src` to `dst` in chunks, updating the provided hasher.

    Args:
        src: Readable binary stream.
        dst: Writable binary stream.
        hasher: Hash object to update as bytes are copied.

    Returns:
        int: Number of bytes copied.
    """
    total = 0
    while True:
        chunk = src.read(1024 * 1024)  # 1 MiB
        if not chunk:
            break
        dst.write(chunk)
        hasher.update(chunk)
        total += len(chunk)
    return total


def save_upload(
    upload_id: str, project_zip: UploadFile, tags_json: UploadFile | None
) -> SavedUpload:
    """
    Persist an uploaded project zip and optional tags json to disk.

    Filenames are normalized to stable names inside the upload directory:
    - `project.zip`
    - `tags.json` (if provided)

    Args:
        upload_id: Upload identifier (directory name).
        project_zip: Required project export zip file.
        tags_json: Optional tags export JSON file.

    Returns:
        SavedUpload: Metadata about the persisted upload.

    Raises:
        OSError: If the filesystem write fails.
        ValueError: If an upload file stream cannot be read.
    """
    d = upload_dir(upload_id)
    d.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256()
    total_bytes = 0

    project_path = d / DEFAULT_PROJECT_ZIP_NAME
    with project_path.open("wb") as f_out:
        if project_zip.file is None:
            raise ValueError("project_zip has no file stream")
        total_bytes += _copy_stream_and_hash(project_zip.file, f_out, hasher)

    tags_rel: str | None = None
    if tags_json is not None:
        tags_path = d / DEFAULT_TAGS_JSON_NAME
        with tags_path.open("wb") as f_out:
            if tags_json.file is None:
                raise ValueError("tags_json has no file stream")
            total_bytes += _copy_stream_and_hash(tags_json.file, f_out, hasher)
        tags_rel = DEFAULT_TAGS_JSON_NAME

    return SavedUpload(
        upload_id=upload_id,
        upload_path=d,
        project_zip_rel=DEFAULT_PROJECT_ZIP_NAME,
        tags_json_rel=tags_rel,
        size_bytes=total_bytes,
        sha256=hasher.hexdigest(),
    )


def get_upload_zip_path(upload_id: str) -> Path:
    """
    Return the path to the saved project zip for the given upload.

    Args:
        upload_id: Upload identifier.

    Returns:
        Path: Absolute path to `<upload_dir>/project.zip`.
    """
    return upload_dir(upload_id) / DEFAULT_PROJECT_ZIP_NAME


def get_tags_json_path(upload_id: str) -> Path | None:
    """
    Return the path to the saved tags JSON for the given upload, if present.

    Args:
        upload_id: Upload identifier.

    Returns:
        Path | None: Absolute path to `<upload_dir>/tags.json` if it exists.
    """
    p = upload_dir(upload_id) / DEFAULT_TAGS_JSON_NAME
    return p if p.exists() else None


def delete_upload_files(upload_id: str) -> None:
    """
    Delete the filesystem directory for a given upload.

    This is a blob cleanup function. Callers should ensure DB state is consistent.

    Args:
        upload_id: Upload identifier.

    Raises:
        OSError: If deletion fails.
    """
    d = upload_dir(upload_id)
    if not d.exists():
        return

    # Python 3.12+: Path.rmdir only works for empty dirs, so use shutil.
    import shutil

    shutil.rmtree(d, ignore_errors=True)
