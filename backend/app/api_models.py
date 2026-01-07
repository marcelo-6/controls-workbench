from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Generic, List, Optional, TypeVar

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
    fields: List[ErrorField] = Field(default_factory=list)


class APIMeta(APIModel):
    request_id: Optional[str] = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


T = TypeVar("T")


class APIResponse(APIModel, Generic[T]):
    status: Status
    message: Optional[str] = None
    data: Optional[T] = None
    meta: APIMeta = Field(default_factory=APIMeta)
    error: Optional[APIError] = None


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
    tools: List[ToolInfo] = Field(default_factory=list)


# --------------------- Uploads ---------------------

class UploadFileInfo(APIModel):
    name: str
    size_bytes: int


class UploadCreated(APIModel):
    upload_id: str
    received_files: List[UploadFileInfo] = Field(default_factory=list)


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
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress_hint: Optional[str] = None
    artifacts_ready: bool = False


class LinesPayload(APIModel):
    lines: List[str] = Field(default_factory=list)


class ArtifactInfo(APIModel):
    path: str
    size_bytes: int
    url: str


class ArtifactsList(APIModel):
    artifacts: List[ArtifactInfo] = Field(default_factory=list)


class RunSummary(APIModel):
    job_id: str
    tool_id: str
    status: JobStatus
    created_at: datetime
    last_accessed_at: datetime


class RecentRuns(APIModel):
    runs: List[RunSummary] = Field(default_factory=list)
