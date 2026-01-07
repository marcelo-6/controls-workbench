from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class APIModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        extra="forbid",
    )


class Status(str, Enum):
    success = "success"
    error = "error"


class ErrorField(APIModel):
    field: str
    message: str


class APIError(APIModel):
    code: str
    detail: str
    fields: list[ErrorField] = Field(default_factory=list)


class APIMeta(APIModel):
    request_id: str | None = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


T = TypeVar("T")


class APIResponse(APIModel, Generic[T]):
    status: Status
    message: str | None = None
    data: T | None = None
    meta: APIMeta = Field(default_factory=APIMeta)
    error: APIError | None = None


# --------------------- Auth ---------------------


class LoginRequest(APIModel):
    password: str


class LoginResponse(APIModel):
    ok: bool


class MeResponse(APIModel):
    ok: bool
    username: str = "user"


# --------------------- Tools ---------------------


class ToolCategory(str, Enum):
    ignition = "Ignition"


class ToolInfo(APIModel):
    tool_id: str
    name: str
    category: ToolCategory
    version: str


class ToolsList(APIModel):
    tools: list[ToolInfo] = Field(default_factory=list)


# --------------------- Uploads ---------------------


class UploadFileInfo(APIModel):
    name: str
    size_bytes: int


class UploadCreated(APIModel):
    upload_id: str
    received_files: list[UploadFileInfo] = Field(default_factory=list)


# --------------------- Jobs ---------------------


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class CreateJobRequest(APIModel):
    tool_id: str
    upload_id: str
    params: dict = Field(default_factory=dict)


class JobCreated(APIModel):
    job_id: str


class JobState(APIModel):
    job_id: str
    tool_id: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_hint: str | None = None
    artifacts_ready: bool = False


class LinesPayload(APIModel):
    lines: list[str] = Field(default_factory=list)


class ArtifactInfo(APIModel):
    path: str
    size_bytes: int
    url: str


class ArtifactsList(APIModel):
    artifacts: list[ArtifactInfo] = Field(default_factory=list)


class RunSummary(APIModel):
    job_id: str
    tool_id: str
    status: JobStatus
    created_at: datetime
    last_accessed_at: datetime


class RecentRuns(APIModel):
    runs: list[RunSummary] = Field(default_factory=list)
