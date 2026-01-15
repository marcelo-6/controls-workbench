# backend/app/domain/uploads/service.py
"""
Uploads domain service.

This module implements the application-level workflow for creating and managing
uploads. An "upload" represents the raw input blobs provided by a user:
- an Ignition project export ZIP (required)
- an optional tags JSON (optional)

Design principles:
- The domain service is HTTP-independent and does not import FastAPI routers.
- All filesystem writes go through `infra.storage.uploads_fs`.
- All persistent state is written to the SQLite catalog via `infra.db.repos.UploadsRepo`.
- Returned objects are plain, serializable domain models that API schemas can wrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from starlette.datastructures import UploadFile

from app.core.time import utcnow
from app.infra.db.repos.uploads import UploadsRepo
from app.infra.storage.uploads_fs import SavedUpload, save_upload


@dataclass(frozen=True)
class UploadCreated:
    """
    Domain result returned after a successful upload creation.

    Attributes:
        upload_id: Stable identifier for the upload row and filesystem directory.
        created_at: UTC timestamp when the upload was persisted.
        project_zip_rel: Relative path of the stored project zip within the upload dir.
        tags_json_rel: Relative path of the optional tags file within the upload dir.
        size_bytes: Total number of bytes written for all upload blobs.
        sha256: SHA-256 checksum of the saved upload content (stable ordering).
    """

    upload_id: str
    created_at: datetime
    project_zip_rel: str
    tags_json_rel: str | None
    size_bytes: int
    sha256: str


class UploadsService:
    """
    Orchestrates upload creation across filesystem storage and the SQLite catalog.

    This service is intentionally small and deterministic, making it a high-ROI
    target for unit tests.
    """

    def __init__(self, uploads_repo: UploadsRepo) -> None:
        """
        Initialize the uploads service.

        Args:
            uploads_repo: Repository used to persist upload metadata in SQLite.
        """
        self._uploads = uploads_repo

    def create_upload(self, project_zip: UploadFile, tags_json: UploadFile | None) -> UploadCreated:
        """
        Create a new upload record and persist upload blobs.

        Workflow:
        1) Generate a new `upload_id`.
        2) Save blobs to the filesystem (`save_upload`).
        3) Insert the upload metadata row into SQLite (`UploadsRepo.create`).

        Args:
            project_zip: Required Ignition project export ZIP.
            tags_json: Optional tags export JSON.

        Returns:
            UploadCreated: Domain result describing the persisted upload.

        Raises:
            Exception: Propagates unexpected infra exceptions; global exception handlers
                      should translate these into standard API errors.
        """
        upload_id = str(uuid4())
        created_at = utcnow()

        saved: SavedUpload = save_upload(upload_id, project_zip, tags_json)

        self._uploads.create(
            upload_id=upload_id,
            created_at=created_at,
            last_accessed_at=created_at,
            project_zip_path=saved.project_zip_rel,
            tags_json_path=saved.tags_json_rel,
            size_bytes=saved.size_bytes,
            sha256=saved.sha256,
        )

        return UploadCreated(
            upload_id=upload_id,
            created_at=created_at,
            project_zip_rel=saved.project_zip_rel,
            tags_json_rel=saved.tags_json_rel,
            size_bytes=saved.size_bytes,
            sha256=saved.sha256,
        )
