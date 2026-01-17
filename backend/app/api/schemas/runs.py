# backend/app/api/schemas/runs.py
"""
Runs (jobs) API schemas.

The UI concept is "run history"; the underlying DB concept is "job".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    """Request payload to create a new run."""

    tool_id: str = Field(alias="toolId")
    upload_id: str = Field(alias="uploadId")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class RunCreated(BaseModel):
    """Response payload returned immediately after creating a run."""

    job_id: str = Field(alias="jobId")

    model_config = {"populate_by_name": True}


class RunStatus(BaseModel):
    """Status payload returned when polling run state."""

    job_id: str = Field(alias="jobId")
    tool_id: str = Field(alias="toolId")
    status: str
    progress: int | None = None
    progress_hint: str | None = Field(default=None, alias="progressHint")
    artifacts_ready: bool = Field(default=False, alias="artifactsReady")
    created_at: str = Field(alias="createdAt")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")

    model_config = {"populate_by_name": True}


class RunSummary(BaseModel):
    """Condensed representation used for recent run listings."""

    job_id: str = Field(alias="jobId")
    tool_id: str = Field(alias="toolId")
    status: str
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class RecentRuns(BaseModel):
    """Wrapper for the recent runs listing."""

    runs: list[RunSummary]
