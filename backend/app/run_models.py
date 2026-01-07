from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import Field

from .api_models import APIModel, JobStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InputFile(APIModel):
    name: str
    size_bytes: int
    sha256: str


class Versions(APIModel):
    app_version: str = "0.1.0"
    parser_version: str = "0.1.0"


class Stats(APIModel):
    parse_seconds: Optional[float] = None
    nodes: Optional[int] = None
    edges: Optional[int] = None
    counts_by_type: Dict[str, int] = Field(default_factory=dict)


class RunMeta(APIModel):
    job_id: str
    tool_id: str
    created_at: datetime = Field(default_factory=utcnow)
    last_accessed_at: datetime = Field(default_factory=utcnow)
    input_files: List[InputFile] = Field(default_factory=list)
    versions: Versions = Field(default_factory=Versions)
    stats: Stats = Field(default_factory=Stats)


class RunState(APIModel):
    job_id: str
    tool_id: str
    status: JobStatus
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress_hint: Optional[str] = None
