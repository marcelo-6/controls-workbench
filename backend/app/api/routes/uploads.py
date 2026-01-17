# backend/app/api/routes/uploads.py
"""
Upload routes.

Uploads are input blobs used to create runs. They are stored on disk and indexed
in the DB for retention and lookup.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_uploads_service, require_auth
from app.api.schemas.uploads import UploadCreated
from app.core.responses import APIResponse, ok
from app.domain.uploads.service import UploadsService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=APIResponse[UploadCreated], dependencies=[Depends(require_auth)])
def create_upload(
    project_zip: UploadFile = File(...),
    tags_json: UploadFile | None = File(default=None),
    svc: UploadsService = Depends(get_uploads_service),
) -> APIResponse[UploadCreated]:
    """
    Create a new upload from multipart form data.

    Args:
        project_zip: Ignition project export zip (required).
        tags_json: Optional Ignition tags export JSON.
        svc: Uploads domain service.

    Returns:
        APIResponse[UploadCreated]: Created upload identifier.
    """
    upload_id = svc.create_upload(project_zip=project_zip, tags_json=tags_json)
    return ok(UploadCreated(uploadId=upload_id))
