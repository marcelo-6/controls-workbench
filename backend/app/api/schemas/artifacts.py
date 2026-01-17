# backend/app/api/schemas/artifacts.py
"""
Artifacts API schemas.

Artifacts are output blobs produced by a run (graph.json, report.json, etc.).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArtifactInfo(BaseModel):
    """Metadata describing an artifact available for download."""

    kind: str
    rel_path: str = Field(alias="relPath")
    content_type: str = Field(alias="contentType")
    size_bytes: int = Field(alias="sizeBytes")
    meta: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class ArtifactsList(BaseModel):
    """Response payload returned when listing artifacts for a run."""

    artifacts: list[ArtifactInfo]
