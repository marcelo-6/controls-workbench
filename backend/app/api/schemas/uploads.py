# backend/app/api/schemas/uploads.py
"""
Uploads API schemas.

Uploads are immutable "blob" inputs used to create jobs/runs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UploadCreated(BaseModel):
    """Response body after successfully creating an upload."""

    upload_id: str = Field(alias="uploadId")

    model_config = {"populate_by_name": True}
